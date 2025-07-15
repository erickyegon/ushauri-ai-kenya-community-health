"""
tools/report_generator.py - Generate formatted reports in text and PDF formats
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import io
import base64
from typing import Dict, Any, Optional
import logging

# PDF generation imports with fallbacks
try:
    from xhtml2pdf import pisa
    PDF_AVAILABLE = True
except ImportError:
    try:
        from weasyprint import HTML, CSS
        PDF_AVAILABLE = True
        USE_WEASYPRINT = True
    except ImportError:
        PDF_AVAILABLE = False
        USE_WEASYPRINT = False

logger = logging.getLogger(__name__)


def format_number(value, decimal_places=1):
    """Format number for display"""
    if pd.isna(value):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:,.{decimal_places}f}"
    return str(value)


def format_percentage(value, decimal_places=1):
    """Format percentage for display"""
    if pd.isna(value):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.{decimal_places}f}%"
    return str(value)


def create_data_table_html(df, title="Data Table", max_rows=50):
    """Convert DataFrame to HTML table"""
    if df is None or df.empty:
        return f"<h3>{title}</h3><p>No data available</p>"
    
    # Limit rows for display
    display_df = df.head(max_rows)
    
    # Format numeric columns
    for col in display_df.columns:
        if display_df[col].dtype in ['float64', 'int64']:
            if 'score' in col.lower() or 'rate' in col.lower() or 'percent' in col.lower():
                display_df[col] = display_df[col].apply(lambda x: format_percentage(x))
            else:
                display_df[col] = display_df[col].apply(lambda x: format_number(x))
    
    table_html = f"""
    <h3>{title}</h3>
    <table class="data-table">
        <thead>
            <tr>
                {''.join(f'<th>{col}</th>' for col in display_df.columns)}
            </tr>
        </thead>
        <tbody>
    """
    
    for _, row in display_df.iterrows():
        table_html += "<tr>"
        for value in row:
            table_html += f"<td>{value}</td>"
        table_html += "</tr>"
    
    table_html += """
        </tbody>
    </table>
    """
    
    if len(df) > max_rows:
        table_html += f"<p><em>Showing {max_rows} of {len(df)} rows</em></p>"
    
    return table_html


def create_chart_html(chart, title="Chart"):
    """Convert Plotly chart to HTML"""
    if chart is None:
        return f"<h3>{title}</h3><p>No chart available</p>"
    
    try:
        # Convert to HTML
        chart_html = pio.to_html(chart, include_plotlyjs='inline', div_id=f"chart_{title.replace(' ', '_')}")
        return f"<h3>{title}</h3>{chart_html}"
    except Exception as e:
        logger.error(f"Error converting chart to HTML: {e}")
        return f"<h3>{title}</h3><p>Chart could not be generated</p>"


def generate_report_text(query: str, result: Dict[str, Any]) -> str:
    """Generate text-based report"""
    
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("KENYA HEALTH DATA ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Query: {query}")
    lines.append("")
    
    # Summary
    if result.get("summary"):
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 40)
        lines.append(result["summary"])
        lines.append("")
    
    # SQL Query
    if result.get("sql_query"):
        lines.append("SQL QUERY EXECUTED")
        lines.append("-" * 40)
        lines.append(result["sql_query"])
        lines.append("")
    
    # Data Table
    if result.get("df") is not None and not result["df"].empty:
        lines.append("DATA RESULTS")
        lines.append("-" * 40)
        
        df = result["df"]
        lines.append(f"Total Records: {len(df)}")
        lines.append(f"Columns: {', '.join(df.columns)}")
        lines.append("")
        
        # Top 10 rows
        lines.append("Sample Data (Top 10 rows):")
        lines.append(df.head(10).to_string(index=False))
        lines.append("")
        
        # Basic statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_cols) > 0:
            lines.append("STATISTICAL SUMMARY")
            lines.append("-" * 40)
            for col in numeric_cols:
                if not df[col].isna().all():
                    mean_val = df[col].mean()
                    min_val = df[col].min()
                    max_val = df[col].max()
                    lines.append(f"{col}:")
                    lines.append(f"  Mean: {format_number(mean_val)}")
                    lines.append(f"  Range: {format_number(min_val)} - {format_number(max_val)}")
            lines.append("")
    
    # Chart description
    if result.get("chart_suggestion"):
        lines.append("VISUALIZATION RECOMMENDATION")
        lines.append("-" * 40)
        lines.append(result["chart_suggestion"])
        lines.append("")
    
    # Footer
    lines.append("=" * 80)
    lines.append("End of Report")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def generate_report_html(query: str, result: Dict[str, Any]) -> str:
    """Generate HTML report"""
    
    # CSS styles
    css_styles = """
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            margin: 10px 0 0 0;
            font-size: 1.1em;
            opacity: 0.9;
        }
        .section {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }
        .section h2 {
            color: #667eea;
            margin-top: 0;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .data-table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        .data-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }
        .data-table tr:nth-child(even) {
            background: #f2f2f2;
        }
        .data-table tr:hover {
            background: #e8f4f8;
        }
        .sql-code {
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            overflow-x: auto;
            margin: 15px 0;
        }
        .summary-box {
            background: #e6f3ff;
            border: 1px solid #b3d9ff;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            border-top: 2px solid #eee;
            color: #666;
        }
    </style>
    """
    
    # Build HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Kenya Health Data Analysis Report</title>
        {css_styles}
    </head>
    <body>
        <div class="header">
            <h1>🇰🇪 Kenya Health Data Analysis</h1>
            <p>Generated on {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}</p>
            <p><strong>Query:</strong> {query}</p>
        </div>
    """
    
    # Executive Summary
    if result.get("summary"):
        html_content += f"""
        <div class="section">
            <h2>📋 Executive Summary</h2>
            <div class="summary-box">
                {result["summary"]}
            </div>
        </div>
        """
    
    # Data Results
    if result.get("df") is not None and not result["df"].empty:
        df = result["df"]
        
        # Statistics cards
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_cols) > 0:
            stats_html = '<div class="stats-grid">'
            stats_html += f'<div class="stat-card"><div class="stat-value">{len(df)}</div><div class="stat-label">Total Records</div></div>'
            stats_html += f'<div class="stat-card"><div class="stat-value">{len(df.columns)}</div><div class="stat-label">Data Columns</div></div>'
            
            # Add key statistics
            for col in numeric_cols[:2]:  # Show stats for first 2 numeric columns
                if not df[col].isna().all():
                    mean_val = df[col].mean()
                    stats_html += f'<div class="stat-card"><div class="stat-value">{format_number(mean_val)}</div><div class="stat-label">Avg {col.replace("_", " ").title()}</div></div>'
            
            stats_html += '</div>'
            
            html_content += f"""
            <div class="section">
                <h2>📊 Data Overview</h2>
                {stats_html}
                {create_data_table_html(df, "Detailed Results")}
            </div>
            """
    
    # Chart
    if result.get("chart"):
        html_content += f"""
        <div class="section">
            <h2>📈 Visualization</h2>
            {create_chart_html(result["chart"], "Data Visualization")}
        </div>
        """
    
    # Chart suggestion
    if result.get("chart_suggestion"):
        html_content += f"""
        <div class="section">
            <h2>💡 Visualization Recommendation</h2>
            <p>{result["chart_suggestion"]}</p>
        </div>
        """
    
    # SQL Query
    if result.get("sql_query"):
        html_content += f"""
        <div class="section">
            <h2>🔍 SQL Query</h2>
            <div class="sql-code">{result["sql_query"]}</div>
        </div>
        """
    
    # Footer
    html_content += f"""
        <div class="footer">
            <p>Generated by Ushauri AI - Kenya Health Data Assistant</p>
            <p>Powered by AutoGen, Streamlit, and PostgreSQL</p>
        </div>
    </body>
    </html>
    """
    
    return html_content


def generate_pdf_report(content: str, is_html: bool = False) -> bytes:
    """Generate PDF from text or HTML content"""
    
    if not PDF_AVAILABLE:
        logger.warning("PDF generation not available - no PDF library installed")
        return None
    
    try:
        if is_html:
            html_content = content
        else:
            # Convert text to HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                    h1, h2 {{ color: #333; }}
                </style>
            </head>
            <body>
                <pre>{content}</pre>
            </body>
            </html>
            """
        
        # Generate PDF using available library
        if 'USE_WEASYPRINT' in globals() and USE_WEASYPRINT:
            # Use WeasyPrint
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            return pdf_buffer.getvalue()
        else:
            # Use xhtml2pdf
            pdf_buffer = io.BytesIO()
            pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
            
            if pisa_status.err:
                logger.error("PDF generation failed")
                return None
            
            return pdf_buffer.getvalue()
    
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None


def generate_report(query: str, result: Dict[str, Any], format_type: str = "text") -> str:
    """
    Main function to generate reports
    
    Args:
        query: User query
        result: Result dictionary from agent workflow
        format_type: "text" or "html"
    
    Returns:
        Formatted report string
    """
    
    if format_type.lower() == "html":
        return generate_report_html(query, result)
    else:
        return generate_report_text(query, result)


def generate_pdf_report_from_result(query: str, result: Dict[str, Any]) -> Optional[bytes]:
    """Generate PDF report from agent result"""
    
    try:
        # Generate HTML report first
        html_report = generate_report_html(query, result)
        
        # Convert to PDF
        pdf_bytes = generate_pdf_report(html_report, is_html=True)
        
        return pdf_bytes
    
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        return None


def create_monthly_chw_report_pdf(engine, county: str = None) -> Optional[bytes]:
    """Generate comprehensive monthly CHW performance PDF report"""
    
    from tools.queries import run_auto_reports
    
    try:
        # Get text report
        text_report = run_auto_reports(engine)
        
        # Convert to HTML with styling
        html_report = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Monthly CHW Performance Report</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    margin: 40px;
                    line-height: 1.6;
                    color: #333;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .section {{
                    margin: 20px 0;
                    padding: 15px;
                    border-left: 4px solid #667eea;
                    background: #f8f9fa;
                }}
                .urgent {{
                    background: #ffe6e6;
                    border-left-color: #ff4444;
                }}
                .warning {{
                    background: #fff3cd;
                    border-left-color: #ffc107;
                }}
                .success {{
                    background: #e8f5e8;
                    border-left-color: #28a745;
                }}
                pre {{
                    white-space: pre-wrap;
                    font-family: inherit;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🇰🇪 Monthly CHW Performance Report</h1>
                <p>{datetime.now().strftime('%B %Y')}</p>
            </div>
            <div class="section">
                <pre>{text_report}</pre>
            </div>
        </body>
        </html>
        """
        
        # Generate PDF
        pdf_bytes = generate_pdf_report(html_report, is_html=True)
        return pdf_bytes
    
    except Exception as e:
        logger.error(f"Error generating monthly CHW report PDF: {e}")
        return None


def export_data_to_excel(df: pd.DataFrame, filename: str = None) -> bytes:
    """Export DataFrame to Excel format"""
    
    if filename is None:
        filename = f"kenya_health_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    try:
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Main data sheet
            df.to_excel(writer, sheet_name='Data', index=False)
            
            # Summary sheet if numeric data exists
            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
            if len(numeric_cols) > 0:
                summary_df = df[numeric_cols].describe()
                summary_df.to_excel(writer, sheet_name='Summary')
        
        buffer.seek(0)
        return buffer.getvalue()
    
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        return None


def create_dashboard_snapshot_html(metrics: Dict[str, Any]) -> str:
    """Create HTML snapshot of dashboard metrics"""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kenya Health Dashboard Snapshot</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
            .metric-card {{ 
                border: 1px solid #ddd; 
                border-radius: 8px; 
                padding: 20px; 
                text-align: center;
                background: #f9f9f9;
            }}
            .metric-value {{ font-size: 2em; font-weight: bold; color: #667eea; }}
            .metric-label {{ color: #666; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>🇰🇪 Kenya Health System Dashboard</h1>
        <p>Snapshot taken: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{format_number(metrics.get('total_chws', 0), 0)}</div>
                <div class="metric-label">Active CHWs</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_percentage(metrics.get('avg_supervision_score', 0))}</div>
                <div class="metric-label">Avg Supervision Score</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_number(metrics.get('total_households', 0), 0)}</div>
                <div class="metric-label">Registered Households</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_number(metrics.get('active_counties', 0), 0)}</div>
                <div class="metric-label">Active Counties</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


# Report templates for different analysis types
REPORT_TEMPLATES = {
    "chw_performance": {
        "title": "CHW Performance Analysis",
        "sections": ["summary", "data", "chart", "recommendations"]
    },
    "county_comparison": {
        "title": "County Comparison Report", 
        "sections": ["summary", "data", "chart", "geographic_insights"]
    },
    "family_planning": {
        "title": "Family Planning Services Report",
        "sections": ["summary", "data", "trends", "service_gaps"]
    },
    "resource_availability": {
        "title": "Resource Availability Assessment",
        "sections": ["summary", "data", "availability_map", "procurement_needs"]
    }
}


def get_report_template(query: str) -> Dict[str, Any]:
    """Determine appropriate report template based on query"""
    
    query_lower = query.lower()
    
    if any(term in query_lower for term in ["chw", "performance", "supervision"]):
        return REPORT_TEMPLATES["chw_performance"]
    elif any(term in query_lower for term in ["county", "region", "comparison"]):
        return REPORT_TEMPLATES["county_comparison"]
    elif any(term in query_lower for term in ["family planning", "fp", "contraception"]):
        return REPORT_TEMPLATES["family_planning"]
    elif any(term in query_lower for term in ["tools", "resources", "equipment"]):
        return REPORT_TEMPLATES["resource_availability"]
    else:
        return {
            "title": "Health Data Analysis Report",
            "sections": ["summary", "data", "chart"]
        }


# Performance summary generators
def generate_performance_summary(df: pd.DataFrame) -> str:
    """Generate performance insights summary"""
    
    if df is None or df.empty:
        return "No data available for performance analysis."
    
    insights = []
    
    # Basic statistics
    total_records = len(df)
    insights.append(f"Analysis covers {total_records} records.")
    
    # Performance insights for supervision data
    if 'avg_score' in df.columns or 'calc_assessment_score' in df.columns:
        score_col = 'avg_score' if 'avg_score' in df.columns else 'calc_assessment_score'
        
        if not df[score_col].isna().all():
            avg_score = df[score_col].mean()
            high_performers = len(df[df[score_col] >= 70])
            low_performers = len(df[df[score_col] < 50])
            
            insights.append(f"Average performance score: {avg_score:.1f}%")
            insights.append(f"High performers (≥70%): {high_performers} ({high_performers/total_records*100:.1f}%)")
            insights.append(f"Need improvement (<50%): {low_performers} ({low_performers/total_records*100:.1f}%)")
    
    # Geographic insights
    if 'county' in df.columns:
        unique_counties = df['county'].nunique()
        insights.append(f"Data covers {unique_counties} counties.")
        
        if 'avg_score' in df.columns:
            best_county = df.loc[df['avg_score'].idxmax(), 'county']
            worst_county = df.loc[df['avg_score'].idxmin(), 'county']
            insights.append(f"Best performing county: {best_county}")
            insights.append(f"County needing most support: {worst_county}")
    
    return " ".join(insights)


def check_report_dependencies():
    """Check if report generation dependencies are available"""
    
    dependencies = {
        "basic_reports": True,  # Always available
        "pdf_generation": PDF_AVAILABLE,
        "excel_export": True,  # pandas always available
        "charts": True  # plotly always available
    }
    
    return dependencies
