import plotly.express as px
import plotly.graph_objects as go
import json
import pandas as pd
import os
from datetime import datetime
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

def plot_tool(params: str, chart_type: str = "line", save_folder: str = "charts", tool_context: ToolContext = None):
    """
    Generate a plotly chart from JSON parameters and save it as an artifact or local file.
    
    Args:
        params (str): JSON string containing 'df', 'x_col', 'y_col'
        chart_type (str): Type of chart ('line', 'bar', 'scatter', 'area')
        save_folder (str): Folder to save the chart image (used only when tool_context is None)
    
    Returns:
        dict: Status and details of the chart generation
    """
    try:
        # Parse the JSON parameters
        data = json.loads(params)
        df_data = data['df']
        x_col = data['x_col']
        y_col = data['y_col']
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(df_data)
        
        # Create the appropriate chart type
        if chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        elif chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        elif chart_type == "area":
            fig = px.area(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        else:
            # Default to line chart
            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        
        # Update layout for better appearance
        fig.update_layout(
            title_font_size=16,
            xaxis_title=x_col.replace('_', ' ').title(),
            yaxis_title=y_col.replace('_', ' ').title(),
            template="plotly_white"
        )
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{chart_type}_{y_col}_vs_{x_col}_{timestamp}.png"
        
        if tool_context:
            # Save as artifact (recommended for ADK)
            img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
            
            artifact_part = types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png"
            )
            
            version = tool_context.save_artifact(filename, artifact_part)
            
            # Track generated charts in state
            charts = tool_context.state.get("generated_charts", [])
            chart_info = {
                "filename": filename,
                "chart_type": chart_type,
                "x_col": x_col,
                "y_col": y_col,
                "timestamp": timestamp,
                "version": version
            }
            charts.append(chart_info)
            tool_context.state["generated_charts"] = charts
            
            return {
                "status": "success",
                "artifact_name": filename,
                "version": version,
                "chart_type": chart_type,
                "message": f"Chart saved as artifact: {filename}"
            }
        else:
            # Fallback to local file saving
            os.makedirs(save_folder, exist_ok=True)
            filepath = os.path.join(save_folder, filename)
            fig.write_image(filepath, width=800, height=600, scale=2)
            
            return {
                "status": "success",
                "filepath": filepath,
                "chart_type": chart_type,
                "message": f"Chart saved to {filepath}"
            }
            
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON format in params"}
    except KeyError as e:
        return {"status": "error", "message": f"Missing key in JSON data: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error generating chart: {e}"}


def list_charts_tool(tool_context: ToolContext = None):
    """
    List all generated charts stored as artifacts.
    
    Returns:
        dict: List of all generated charts with their details
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext required for artifact access"}
    
    try:
        # Get list of all artifacts
        artifacts = tool_context.list_artifacts()
        
        # Filter for chart artifacts (PNG files)
        chart_artifacts = [f for f in artifacts if f.endswith('.png')]
        
        # Get chart history from state
        charts_history = tool_context.state.get("generated_charts", [])
        
        return {
            "status": "success",
            "chart_artifacts": chart_artifacts,
            "charts_history": charts_history,
            "total_charts": len(chart_artifacts),
            "message": f"Found {len(chart_artifacts)} chart artifacts"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error listing charts: {e}"}


def load_chart_tool(chart_filename: str, tool_context: ToolContext = None):
    """
    Load a previously generated chart artifact.
    
    Args:
        chart_filename (str): Name of the chart file to load
    
    Returns:
        dict: Status and chart information
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext required for artifact access"}
    
    try:
        # Load the artifact
        chart_part = tool_context.load_artifact(chart_filename)
        
        if not chart_part:
            return {
                "status": "error", 
                "message": f"Chart '{chart_filename}' not found in artifacts"
            }
        
        # Get chart info from state if available
        charts_history = tool_context.state.get("generated_charts", [])
        chart_info = None
        for chart in charts_history:
            if chart["filename"] == chart_filename:
                chart_info = chart
                break
        
        return {
            "status": "success",
            "chart_filename": chart_filename,
            "chart_info": chart_info,
            "mime_type": chart_part.inline_data.mime_type if hasattr(chart_part, 'inline_data') else "image/png",
            "message": f"Chart '{chart_filename}' loaded successfully"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error loading chart: {e}"}


def delete_chart_tool(chart_filename: str, tool_context: ToolContext = None):
    """
    Delete a chart from artifacts and update state.
    Note: This removes it from tracking but ADK may still store the artifact.
    
    Args:
        chart_filename (str): Name of the chart file to delete from tracking
    
    Returns:
        dict: Status of the deletion operation
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext required for state management"}
    
    try:
        # Remove from state tracking
        charts_history = tool_context.state.get("generated_charts", [])
        updated_charts = [chart for chart in charts_history if chart["filename"] != chart_filename]
        
        if len(updated_charts) == len(charts_history):
            return {
                "status": "warning",
                "message": f"Chart '{chart_filename}' was not found in tracking history"
            }
        
        tool_context.state["generated_charts"] = updated_charts
        
        return {
            "status": "success",
            "message": f"Chart '{chart_filename}' removed from tracking. {len(charts_history) - len(updated_charts)} chart(s) removed."
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error deleting chart: {e}"}
plot_tool=FunctionTool(plot_tool)
load_chart_tool=FunctionTool(load_chart_tool)
list_charts_tool=FunctionTool(list_charts_tool)
