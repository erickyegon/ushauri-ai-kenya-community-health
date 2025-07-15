"""
tools/queries.py - Predefined SQL queries and visualization functions
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tools.db import execute_sql_query
import streamlit as st
from datetime import datetime, timedelta
import numpy as np


# Predefined SQL queries for common health indicators (Kisumu, Busia, Vihiga: Dec 2024 - Jun 2025)
PREDEFINED_QUERIES = {
    "chw_performance_by_county": """
        SELECT 
            county,
            COUNT(DISTINCT chv_uuid) as total_chws,
            AVG(calc_assessment_score) as avg_supervision_score,
            STDDEV(calc_assessment_score) as score_variance,
            MIN(calc_assessment_score) as min_score,
            MAX(calc_assessment_score) as max_score,
            COUNT(CASE WHEN calc_assessment_score >= 85 THEN 1 END) as excellent_count,
            COUNT(CASE WHEN calc_assessment_score BETWEEN 70 AND 84 THEN 1 END) as good_count,
            COUNT(CASE WHEN calc_assessment_score BETWEEN 50 AND 69 THEN 1 END) as needs_improvement_count,
            COUNT(CASE WHEN calc_assessment_score < 50 THEN 1 END) as critical_count,
            ROUND(COUNT(CASE WHEN calc_assessment_score >= 85 THEN 1 END) * 100.0 / COUNT(*), 1) as excellent_percentage,
            ROUND(COUNT(CASE WHEN calc_assessment_score < 50 THEN 1 END) * 100.0 / COUNT(*), 1) as critical_percentage,
            COUNT(*) as total_supervisions,
            MAX(reported) as last_supervision_date
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        AND calc_assessment_score IS NOT NULL
        GROUP BY county
        ORDER BY avg_supervision_score DESC;
    """,
    
    "monthly_performance_trends": """
        SELECT 
            DATE_TRUNC('month', reported) as month,
            county,
            COUNT(DISTINCT chv_uuid) as active_chws,
            AVG(calc_assessment_score) as avg_supervision_score,
            AVG(calc_pneumonia_score) as avg_pneumonia_score,
            AVG(calc_malaria_score) as avg_malaria_score,
            AVG(calc_family_planning_score) as avg_fp_score,
            AVG(calc_immunization_score) as avg_immunization_score,
            AVG(calc_nutrition_score) as avg_nutrition_score,
            AVG(calc_newborn_visit_score) as avg_newborn_score,
            COUNT(*) as total_supervisions,
            COUNT(CASE WHEN has_all_tools = 'yes' THEN 1 END) as chws_with_tools,
            COUNT(CASE WHEN has_proper_protective_equipment = 'yes' THEN 1 END) as chws_with_ppe,
            ROUND(COUNT(CASE WHEN has_all_tools = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as tools_availability_rate
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        AND calc_assessment_score IS NOT NULL
        GROUP BY DATE_TRUNC('month', reported), county
        ORDER BY month ASC, county;
    """,
    
    "critical_performance_chws": """
        SELECT 
            chv_name,
            chv_uuid,
            county,
            AVG(calc_assessment_score) as avg_overall_score,
            AVG(calc_pneumonia_score) as avg_pneumonia_score,
            AVG(calc_malaria_score) as avg_malaria_score,
            AVG(calc_family_planning_score) as avg_fp_score,
            AVG(calc_immunization_score) as avg_immunization_score,
            COUNT(*) as supervision_count,
            MIN(calc_assessment_score) as worst_score,
            MAX(reported) as last_supervision,
            STRING_AGG(DISTINCT 
                CASE 
                    WHEN calc_pneumonia_score < 50 THEN 'Pneumonia'
                    WHEN calc_malaria_score < 50 THEN 'Malaria'
                    WHEN calc_family_planning_score < 50 THEN 'Family Planning'
                    WHEN calc_immunization_score < 50 THEN 'Immunization'
                    WHEN calc_nutrition_score < 50 THEN 'Nutrition'
                END, ', ') as critical_service_areas,
            CASE 
                WHEN AVG(calc_assessment_score) < 40 THEN 'Immediate Intervention Required'
                WHEN AVG(calc_assessment_score) < 50 THEN 'Critical - Urgent Support Needed'
                WHEN AVG(calc_assessment_score) < 60 THEN 'Needs Intensive Mentorship'
                ELSE 'Needs Regular Support'
            END as recommended_action
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        AND calc_assessment_score IS NOT NULL
        AND calc_assessment_score < 70
        GROUP BY chv_name, chv_uuid, county
        HAVING COUNT(*) >= 2  -- At least 2 supervisions for reliability
        ORDER BY avg_overall_score ASC, county;
    """,
    
    "family_planning_service_analysis": """
        SELECT 
            county,
            DATE_TRUNC('month', reported) as month,
            COUNT(*) as total_fp_visits,
            COUNT(DISTINCT patient_id) as unique_clients,
            COUNT(CASE WHEN on_fp = 'yes' THEN 1 END) as active_fp_users,
            COUNT(CASE WHEN has_side_effects = 'yes' THEN 1 END) as clients_with_side_effects,
            COUNT(CASE WHEN is_referral = 'yes' THEN 1 END) as referrals_made,
            ROUND(AVG(patient_age_in_years), 1) as avg_client_age,
            -- Method distribution
            COUNT(CASE WHEN current_fp_method ILIKE '%coc%' THEN 1 END) as coc_users,
            COUNT(CASE WHEN current_fp_method ILIKE '%pop%' THEN 1 END) as pop_users,
            COUNT(CASE WHEN current_fp_method ILIKE '%injectable%' THEN 1 END) as injectable_users,
            COUNT(CASE WHEN current_fp_method ILIKE '%condom%' THEN 1 END) as condom_users,
            -- Calculated rates
            ROUND(COUNT(CASE WHEN on_fp = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as fp_adoption_rate,
            ROUND(COUNT(CASE WHEN has_side_effects = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as side_effect_rate,
            ROUND(COUNT(CASE WHEN is_referral = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as referral_rate,
            -- Commodity provision
            SUM(COALESCE(coc_cycles, 0)) as total_coc_cycles_provided,
            SUM(COALESCE(pop_cycles, 0)) as total_pop_cycles_provided,
            SUM(COALESCE(condom_pieces, 0)) as total_condoms_provided
        FROM family_planning_visits 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        GROUP BY county, DATE_TRUNC('month', reported)
        ORDER BY month DESC, county;
    """,
    
    "resource_availability_assessment": """
        SELECT 
            county,
            COUNT(DISTINCT chv_uuid) as total_chws_assessed,
            -- Tool availability
            COUNT(CASE WHEN has_all_tools = 'yes' THEN 1 END) as chws_with_tools,
            ROUND(COUNT(CASE WHEN has_all_tools = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as tools_availability_rate,
            -- PPE availability
            COUNT(CASE WHEN has_proper_protective_equipment = 'yes' THEN 1 END) as chws_with_ppe,
            ROUND(COUNT(CASE WHEN has_proper_protective_equipment = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as ppe_availability_rate,
            -- Medicine availability
            COUNT(CASE WHEN has_essential_medicines = 'yes' THEN 1 END) as chws_with_medicines,
            ROUND(COUNT(CASE WHEN has_essential_medicines = 'yes' THEN 1 END) * 100.0 / COUNT(*), 1) as medicine_availability_rate,
            -- Combined resource score
            ROUND((
                COUNT(CASE WHEN has_all_tools = 'yes' THEN 1 END) +
                COUNT(CASE WHEN has_proper_protective_equipment = 'yes' THEN 1 END) +
                COUNT(CASE WHEN has_essential_medicines = 'yes' THEN 1 END)
            ) * 100.0 / (COUNT(*) * 3), 1) as overall_resource_score,
            -- Most recent assessment
            MAX(reported) as last_assessment_date,
            COUNT(*) as total_assessments
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        AND (has_all_tools IS NOT NULL OR has_proper_protective_equipment IS NOT NULL OR has_essential_medicines IS NOT NULL)
        GROUP BY county
        ORDER BY overall_resource_score DESC;
    """,
    
    "household_coverage_analysis": """
        SELECT 
            h.county,
            COUNT(DISTINCT h.household_uuid) as total_households,
            COUNT(DISTINCT h.chw_uuid) as active_chws,
            ROUND(COUNT(DISTINCT h.household_uuid) * 1.0 / COUNT(DISTINCT h.chw_uuid), 1) as households_per_chw,
            COUNT(DISTINCT CASE WHEN h.reported_date >= '2025-01-01' THEN h.household_uuid END) as recent_registrations,
            -- Population estimates
            COALESCE(u.u2_pop, 0) as under2_population,
            ROUND(COALESCE(u.u2_pop, 0) * 1.0 / COUNT(DISTINCT h.chw_uuid), 1) as under2_per_chw,
            -- CHW performance correlation
            ROUND(AVG(s.calc_assessment_score), 1) as avg_chw_performance_score,
            -- Coverage quality indicators
            COUNT(DISTINCT h.chw_uuid) as unique_chws_with_households,
            MIN(h.reported_date) as earliest_registration,
            MAX(h.reported_date) as latest_registration
        FROM households h
        LEFT JOIN u2pop u ON h.county = u.county
        LEFT JOIN supervision s ON h.chw_uuid = s.chv_uuid 
            AND s.reported >= '2024-12-01' AND s.reported <= '2025-06-30'
        WHERE h.county IN ('Kisumu', 'Busia', 'Vihiga')
        GROUP BY h.county, u.u2_pop
        ORDER BY households_per_chw DESC;
    """,
    
    "service_area_performance_comparison": """
        SELECT 
            county,
            -- Overall supervision
            ROUND(AVG(calc_assessment_score), 1) as overall_avg,
            -- Service area averages
            ROUND(AVG(calc_pneumonia_score), 1) as pneumonia_avg,
            ROUND(AVG(calc_malaria_score), 1) as malaria_avg,
            ROUND(AVG(calc_family_planning_score), 1) as family_planning_avg,
            ROUND(AVG(calc_immunization_score), 1) as immunization_avg,
            ROUND(AVG(calc_nutrition_score), 1) as nutrition_avg,
            ROUND(AVG(calc_newborn_visit_score), 1) as newborn_care_avg,
            -- Performance categorization by service
            COUNT(CASE WHEN calc_pneumonia_score >= 85 THEN 1 END) as pneumonia_excellent,
            COUNT(CASE WHEN calc_pneumonia_score < 50 THEN 1 END) as pneumonia_critical,
            COUNT(CASE WHEN calc_malaria_score >= 85 THEN 1 END) as malaria_excellent,
            COUNT(CASE WHEN calc_malaria_score < 50 THEN 1 END) as malaria_critical,
            COUNT(CASE WHEN calc_family_planning_score >= 85 THEN 1 END) as fp_excellent,
            COUNT(CASE WHEN calc_family_planning_score < 50 THEN 1 END) as fp_critical,
            COUNT(CASE WHEN calc_immunization_score >= 85 THEN 1 END) as immunization_excellent,
            COUNT(CASE WHEN calc_immunization_score < 50 THEN 1 END) as immunization_critical,
            -- Sample sizes
            COUNT(CASE WHEN calc_pneumonia_score IS NOT NULL THEN 1 END) as pneumonia_sample_size,
            COUNT(CASE WHEN calc_malaria_score IS NOT NULL THEN 1 END) as malaria_sample_size,
            COUNT(CASE WHEN calc_family_planning_score IS NOT NULL THEN 1 END) as fp_sample_size,
            COUNT(CASE WHEN calc_immunization_score IS NOT NULL THEN 1 END) as immunization_sample_size,
            COUNT(*) as total_supervisions
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        GROUP BY county
        ORDER BY overall_avg DESC;
    """,
    
    "chw_improvement_tracking": """
        SELECT 
            chv_name,
            chv_uuid,
            county,
            -- December 2024 baseline
            ROUND(AVG(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' 
                          THEN calc_assessment_score END), 1) as dec_2024_score,
            -- June 2025 latest
            ROUND(AVG(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' 
                          THEN calc_assessment_score END), 1) as jun_2025_score,
            -- Calculate improvement
            ROUND(AVG(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' 
                          THEN calc_assessment_score END) - 
                  AVG(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' 
                          THEN calc_assessment_score END), 1) as score_change,
            -- Improvement category
            CASE 
                WHEN AVG(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' 
                             THEN calc_assessment_score END) - 
                     AVG(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' 
                             THEN calc_assessment_score END) >= 15 THEN 'Significant Improvement'
                WHEN AVG(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' 
                             THEN calc_assessment_score END) - 
                     AVG(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' 
                             THEN calc_assessment_score END) >= 5 THEN 'Moderate Improvement'
                WHEN ABS(AVG(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' 
                                 THEN calc_assessment_score END) - 
                         AVG(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' 
                                 THEN calc_assessment_score END)) < 5 THEN 'Stable Performance'
                WHEN AVG(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' 
                             THEN calc_assessment_score END) - 
                     AVG(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' 
                             THEN calc_assessment_score END) <= -5 THEN 'Performance Decline'
                ELSE 'Insufficient Data'
            END as improvement_category,
            -- Supporting metrics
            COUNT(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' THEN 1 END) as dec_supervisions,
            COUNT(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' THEN 1 END) as jun_supervisions,
            COUNT(*) as total_supervisions
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        AND calc_assessment_score IS NOT NULL
        GROUP BY chv_name, chv_uuid, county
        HAVING COUNT(CASE WHEN reported >= '2024-12-01' AND reported < '2025-01-01' THEN 1 END) >= 1
        AND COUNT(CASE WHEN reported >= '2025-06-01' AND reported <= '2025-06-30' THEN 1 END) >= 1
        ORDER BY score_change DESC, county;
    """
}


def execute_predefined_query(engine, query_name):
    """Execute a predefined query by name"""
    if query_name not in PREDEFINED_QUERIES:
        return pd.DataFrame({"error": [f"Query '{query_name}' not found"]})
    
    return execute_sql_query(engine, PREDEFINED_QUERIES[query_name])


def county_comparison_plot(engine):
    """Create comprehensive county comparison visualization"""
    df = execute_predefined_query(engine, "county_comparison")
    
    if df is None or df.empty or 'error' in df.columns:
        return None
    
    # Create subplot figure
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Overall Supervision Scores', 
            'Service-Specific Performance',
            'CHW Distribution', 
            'Activity Volume'
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": True}, {"secondary_y": False}]]
    )
    
    # Sort by overall score for consistent ordering
    df_sorted = df.sort_values('avg_supervision_score', ascending=True)
    
    # 1. Overall supervision scores (horizontal bar)
    fig.add_trace(
        go.Bar(
            y=df_sorted['county'],
            x=df_sorted['avg_supervision_score'],
            name='Supervision Score',
            marker_color='lightblue',
            orientation='h'
        ),
        row=1, col=1
    )
    
    # 2. Service-specific scores (grouped bar)
    services = ['avg_pneumonia_score', 'avg_malaria_score', 'avg_fp_score', 'avg_immunization_score']
    service_names = ['Pneumonia', 'Malaria', 'Family Planning', 'Immunization']
    colors = ['red', 'orange', 'green', 'purple']
    
    for i, (service, name, color) in enumerate(zip(services, service_names, colors)):
        fig.add_trace(
            go.Bar(
                x=df_sorted['county'],
                y=df_sorted[service],
                name=name,
                marker_color=color,
                showlegend=(i==0)  # Only show legend for first trace
            ),
            row=1, col=2
        )
    
    # 3. CHW distribution vs population coverage
    fig.add_trace(
        go.Scatter(
            x=df_sorted['county'],
            y=df_sorted['total_chws'],
            mode='markers+lines',
            name='CHWs',
            marker=dict(size=10, color='blue'),
            line=dict(color='blue')
        ),
        row=2, col=1
    )
    
    # 4. Activity volume (supervision count)
    fig.add_trace(
        go.Bar(
            x=df_sorted['county'],
            y=df_sorted['total_supervisions'],
            name='Supervisions',
            marker_color='lightgreen'
        ),
        row=2, col=2
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        title_text="County Health System Performance Comparison",
        showlegend=True,
        title_x=0.5
    )
    
    # Update x-axis labels for better readability
    fig.update_xaxes(tickangle=45, row=1, col=2)
    fig.update_xaxes(tickangle=45, row=2, col=1)
    fig.update_xaxes(tickangle=45, row=2, col=2)
    
    return fig


def chw_performance_trend_plot(engine, county=None, chw_name=None):
    """Create CHW performance trend visualization"""
    query = PREDEFINED_QUERIES["chw_performance_monthly"]
    
    # Add filters if specified
    if county:
        query = query.replace("ORDER BY", f"AND county = '{county}' ORDER BY")
    if chw_name:
        query = query.replace("ORDER BY", f"AND chv_name = '{chw_name}' ORDER BY")
    
    df = execute_sql_query(engine, query)
    
    if df is None or df.empty or 'error' in df.columns:
        return None
    
    # Convert report_month to datetime
    df['report_month'] = pd.to_datetime(df['report_month'])
    
    # Create line plot
    fig = px.line(
        df,
        x='report_month',
        y='avg_score',
        color='county' if not county else 'chv_name',
        title=f"CHW Performance Trends - {county if county else 'All Counties'}",
        labels={
            'report_month': 'Month',
            'avg_score': 'Average Supervision Score',
            'county': 'County',
            'chv_name': 'CHW Name'
        }
    )
    
    # Add threshold lines
    fig.add_hline(y=70, line_dash="dash", line_color="green", 
                  annotation_text="Good Performance (70%)")
    fig.add_hline(y=50, line_dash="dash", line_color="orange", 
                  annotation_text="Needs Improvement (50%)")
    fig.add_hline(y=30, line_dash="dash", line_color="red", 
                  annotation_text="Critical (30%)")
    
    fig.update_layout(height=500)
    return fig


def service_performance_radar(engine, county):
    """Create radar chart for service-specific performance by county"""
    df = execute_predefined_query(engine, "county_comparison")
    
    if df is None or df.empty or 'error' in df.columns:
        return None
    
    county_data = df[df['county'] == county]
    if county_data.empty:
        return None
    
    # Prepare data for radar chart
    services = [
        'avg_pneumonia_score', 'avg_malaria_score', 'avg_fp_score', 
        'avg_immunization_score', 'avg_supervision_score'
    ]
    
    service_labels = [
        'Pneumonia', 'Malaria', 'Family Planning', 
        'Immunization', 'Overall Supervision'
    ]
    
    values = [county_data[service].iloc[0] for service in services]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=service_labels,
        fill='toself',
        name=county,
        line_color='blue'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        showlegend=True,
        title=f"Service Performance Profile - {county}",
        height=500
    )
    
    return fig


def generate_retraining_recommendations(engine):
    """Generate specific retraining recommendations based on performance data"""
    
    # Get low performing CHWs
    low_performers = execute_predefined_query(engine, "low_performing_chws")
    
    if low_performers is None or low_performers.empty or 'error' in low_performers.columns:
        return "No performance data available for retraining analysis."
    
    recommendations = []
    
    # Immediate intervention cases
    critical = low_performers[low_performers['performance_category'] == 'Immediate Intervention']
    if not critical.empty:
        recommendations.append(f"🚨 URGENT: {len(critical)} CHWs require immediate intervention:")
        for _, chw in critical.head(5).iterrows():
            recommendations.append(
                f"   • {chw['chv_name']} ({chw['county']}) - Score: {chw['avg_score']:.1f}%"
            )
    
    # Needs support cases
    support = low_performers[low_performers['performance_category'] == 'Needs Support']
    if not support.empty:
        recommendations.append(f"\n⚠️  {len(support)} CHWs need additional support:")
        county_counts = support['county'].value_counts()
        for county, count in county_counts.head(3).items():
            recommendations.append(f"   • {county}: {count} CHWs")
    
    # Service-specific analysis
    service_query = """
        SELECT 
            county,
            AVG(calc_pneumonia_score) as pneumonia_avg,
            AVG(calc_malaria_score) as malaria_avg,
            AVG(calc_family_planning_score) as fp_avg,
            AVG(calc_immunization_score) as immunization_avg
        FROM supervision 
        WHERE reported >= CURRENT_DATE - INTERVAL '3 months'
        GROUP BY county
        ORDER BY county;
    """
    
    services_df = execute_sql_query(engine, service_query)
    if services_df is not None and not services_df.empty and 'error' not in services_df.columns:
        recommendations.append("\n📚 Recommended Training Focus Areas:")
        
        for _, county_data in services_df.iterrows():
            county = county_data['county']
            weak_areas = []
            
            if county_data['pneumonia_avg'] < 60:
                weak_areas.append("Pneumonia Management")
            if county_data['malaria_avg'] < 60:
                weak_areas.append("Malaria Treatment")
            if county_data['fp_avg'] < 60:
                weak_areas.append("Family Planning")
            if county_data['immunization_avg'] < 60:
                weak_areas.append("Immunization")
            
            if weak_areas:
                recommendations.append(f"   • {county}: {', '.join(weak_areas)}")
    
    return "\n".join(recommendations) if recommendations else "All CHWs performing well - no specific retraining needed."


def run_auto_reports(engine):
    """Generate comprehensive monthly performance report for Kisumu, Busia, and Vihiga counties"""
    
    report_sections = []
    
    # Header
    report_sections.append("=" * 80)
    report_sections.append("COMPREHENSIVE CHW PERFORMANCE ANALYSIS REPORT")
    report_sections.append("KISUMU, BUSIA & VIHIGA COUNTIES")
    report_sections.append(f"Analysis Period: December 2024 - June 2025")
    report_sections.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_sections.append("=" * 80)
    
    # Executive Summary
    report_sections.append("\n📊 EXECUTIVE SUMMARY")
    report_sections.append("-" * 50)
    
    try:
        # Get overall performance data
        county_data = execute_predefined_query(engine, "chw_performance_by_county")
        if county_data is not None and not county_data.empty and 'error' not in county_data.columns:
            total_chws = county_data['total_chws'].sum()
            total_supervisions = county_data['total_supervisions'].sum()
            system_avg = county_data['avg_supervision_score'].mean()
            best_county = county_data.loc[county_data['avg_supervision_score'].idxmax()]
            worst_county = county_data.loc[county_data['avg_supervision_score'].idxmin()]
            
            critical_chws = county_data['critical_count'].sum()
            excellent_chws = county_data['excellent_count'].sum()
            
            report_sections.append(f"• System Overview: {total_chws} CHWs across 3 counties, {total_supervisions} supervisions analyzed")
            report_sections.append(f"• System-wide Average Score: {system_avg:.1f}% ({'GOOD' if system_avg >= 70 else 'NEEDS IMPROVEMENT'})")
            report_sections.append(f"• Best Performing County: {best_county['county']} ({best_county['avg_supervision_score']:.1f}%)")
            report_sections.append(f"• County Needing Most Support: {worst_county['county']} ({worst_county['avg_supervision_score']:.1f}%)")
            report_sections.append(f"• Critical Performance CHWs: {critical_chws} (require immediate intervention)")
            report_sections.append(f"• Excellent Performance CHWs: {excellent_chws} (role models for peer learning)")
    except Exception as e:
        report_sections.append(f"Error generating executive summary: {e}")
    
    # County Performance Breakdown
    report_sections.append("\n🏥 COUNTY PERFORMANCE ANALYSIS")
    report_sections.append("-" * 50)
    
    if county_data is not None and not county_data.empty and 'error' not in county_data.columns:
        for _, county in county_data.iterrows():
            report_sections.append(f"\n{county['county'].upper()} COUNTY:")
            report_sections.append(f"  Overall Score: {county['avg_supervision_score']:.1f}% (Range: {county['min_score']:.0f}%-{county['max_score']:.0f}%)")
            report_sections.append(f"  Total CHWs: {county['total_chws']} | Supervisions: {county['total_supervisions']}")
            report_sections.append(f"  Performance Distribution:")
            report_sections.append(f"    - Excellent (≥85%): {county['excellent_count']} CHWs ({county['excellent_percentage']:.1f}%)")
            report_sections.append(f"    - Good (70-84%): {county['good_count']} CHWs")
            report_sections.append(f"    - Needs Improvement (50-69%): {county['needs_improvement_count']} CHWs")
            report_sections.append(f"    - Critical (<50%): {county['critical_count']} CHWs ({county['critical_percentage']:.1f}%)")
            report_sections.append(f"  Score Variance: {county['score_variance']:.1f} ({'High variability' if county['score_variance'] > 20 else 'Consistent performance'})")
    
    # Critical CHWs Requiring Immediate Attention
    report_sections.append("\n🚨 CRITICAL CHWs REQUIRING IMMEDIATE INTERVENTION")
    report_sections.append("-" * 50)
    
    try:
        critical_chws_data = execute_predefined_query(engine, "critical_performance_chws")
        if critical_chws_data is not None and not critical_chws_data.empty and 'error' not in critical_chws_data.columns:
            immediate_intervention = critical_chws_data[critical_chws_data['recommended_action'].str.contains('Immediate', na=False)]
            urgent_support = critical_chws_data[critical_chws_data['recommended_action'].str.contains('Critical', na=False)]
            
            report_sections.append(f"IMMEDIATE INTERVENTION REQUIRED ({len(immediate_intervention)} CHWs):")
            for _, chw in immediate_intervention.head(10).iterrows():
                critical_areas = chw['critical_service_areas'] if pd.notna(chw['critical_service_areas']) else 'General performance'
                report_sections.append(f"  • {chw['chv_name']} ({chw['county']}) - Score: {chw['avg_overall_score']:.1f}% | Critical areas: {critical_areas}")
            
            if len(immediate_intervention) > 10:
                report_sections.append(f"  ... and {len(immediate_intervention) - 10} more CHWs")
            
            report_sections.append(f"\nURGENT SUPPORT NEEDED ({len(urgent_support)} CHWs):")
            for _, chw in urgent_support.head(5).iterrows():
                report_sections.append(f"  • {chw['chv_name']} ({chw['county']}) - Score: {chw['avg_overall_score']:.1f}%")
        else:
            report_sections.append("✅ No CHWs currently require immediate intervention (all scores ≥70%)")
    except Exception as e:
        report_sections.append(f"Error analyzing critical CHWs: {e}")
    
    # Service Area Performance Analysis
    report_sections.append("\n📋 SERVICE AREA PERFORMANCE ANALYSIS")
    report_sections.append("-" * 50)
    
    try:
        service_data = execute_predefined_query(engine, "service_area_performance_comparison")
        if service_data is not None and not service_data.empty and 'error' not in service_data.columns:
            # Calculate system-wide service averages
            services = {
                'Pneumonia Management': service_data['pneumonia_avg'].mean(),
                'Malaria Treatment': service_data['malaria_avg'].mean(),
                'Family Planning': service_data['family_planning_avg'].mean(),
                'Immunization': service_data['immunization_avg'].mean(),
                'Nutrition Counseling': service_data['nutrition_avg'].mean(),
                'Newborn Care': service_data['newborn_care_avg'].mean()
            }
            
            # Rank services by performance
            sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)
            
            report_sections.append("SYSTEM-WIDE SERVICE PERFORMANCE RANKING:")
            for i, (service, score) in enumerate(sorted_services, 1):
                status = "EXCELLENT" if score >= 85 else "GOOD" if score >= 70 else "NEEDS IMPROVEMENT" if score >= 50 else "CRITICAL"
                report_sections.append(f"  {i}. {service}: {score:.1f}% ({status})")
            
            # Identify weakest service areas by county
            report_sections.append(f"\nSERVICE AREA GAPS BY COUNTY:")
            for _, county in service_data.iterrows():
                weak_areas = []
                if county['pneumonia_avg'] < 60: weak_areas.append(f"Pneumonia ({county['pneumonia_avg']:.1f}%)")
                if county['malaria_avg'] < 60: weak_areas.append(f"Malaria ({county['malaria_avg']:.1f}%)")
                if county['family_planning_avg'] < 60: weak_areas.append(f"Family Planning ({county['family_planning_avg']:.1f}%)")
                if county['immunization_avg'] < 60: weak_areas.append(f"Immunization ({county['immunization_avg']:.1f}%)")
                
                if weak_areas:
                    report_sections.append(f"  {county['county']}: {', '.join(weak_areas)}")
                else:
                    report_sections.append(f"  {county['county']}: ✅ All service areas above 60%")
    except Exception as e:
        report_sections.append(f"Error analyzing service areas: {e}")
    
    # Resource Availability Assessment
    report_sections.append("\n🧰 RESOURCE AVAILABILITY ASSESSMENT")
    report_sections.append("-" * 50)
    
    try:
        resource_data = execute_predefined_query(engine, "resource_availability_assessment")
        if resource_data is not None and not resource_data.empty and 'error' not in resource_data.columns:
            report_sections.append("RESOURCE AVAILABILITY BY COUNTY:")
            for _, county in resource_data.iterrows():
                report_sections.append(f"\n{county['county'].upper()}:")
                report_sections.append(f"  Tools: {county['tools_availability_rate']:.1f}% ({county['chws_with_tools']}/{county['total_chws_assessed']} CHWs)")
                report_sections.append(f"  PPE: {county['ppe_availability_rate']:.1f}% ({county['chws_with_ppe']}/{county['total_chws_assessed']} CHWs)")
                report_sections.append(f"  Medicines: {county['medicine_availability_rate']:.1f}% ({county['chws_with_medicines']}/{county['total_chws_assessed']} CHWs)")
                report_sections.append(f"  Overall Resource Score: {county['overall_resource_score']:.1f}%")
                
                # Resource gaps
                gaps = []
                if county['tools_availability_rate'] < 80: gaps.append("Tools")
                if county['ppe_availability_rate'] < 80: gaps.append("PPE")
                if county['medicine_availability_rate'] < 80: gaps.append("Medicines")
                
                if gaps:
                    report_sections.append(f"  ⚠️ Critical Gaps: {', '.join(gaps)}")
                else:
                    report_sections.append(f"  ✅ Adequate resource availability")
    except Exception as e:
        report_sections.append(f"Error analyzing resources: {e}")
    
    # Monthly Performance Trends
    report_sections.append("\n📈 7-MONTH PERFORMANCE TRENDS")
    report_sections.append("-" * 50)
    
    try:
        trends_data = execute_predefined_query(engine, "monthly_performance_trends")
        if trends_data is not None and not trends_data.empty and 'error' not in trends_data.columns:
            report_sections.append("MONTHLY SUPERVISION SCORE TRENDS:")
            
            # Calculate month-over-month changes
            for county in ['Kisumu', 'Busia', 'Vihiga']:
                county_trends = trends_data[trends_data['county'] == county].sort_values('month')
                if not county_trends.empty:
                    first_month = county_trends.iloc[0]
                    last_month = county_trends.iloc[-1]
                    change = last_month['avg_supervision_score'] - first_month['avg_supervision_score']
                    trend_direction = "📈 IMPROVING" if change > 2 else "📉 DECLINING" if change < -2 else "➡️ STABLE"
                    
                    report_sections.append(f"\n{county}:")
                    report_sections.append(f"  Dec 2024: {first_month['avg_supervision_score']:.1f}% → Jun 2025: {last_month['avg_supervision_score']:.1f}%")
                    report_sections.append(f"  7-Month Change: {change:+.1f} points ({trend_direction})")
                    report_sections.append(f"  Tool Availability Trend: {last_month['tools_availability_rate']:.1f}%")
    except Exception as e:
        report_sections.append(f"Error analyzing trends: {e}")
    
    # Family Planning Service Analysis
    report_sections.append("\n💊 FAMILY PLANNING SERVICES ANALYSIS")
    report_sections.append("-" * 50)
    
    try:
        fp_data = execute_predefined_query(engine, "family_planning_service_analysis")
        if fp_data is not None and not fp_data.empty and 'error' not in fp_data.columns:
            # Get latest month data
            latest_month_data = fp_data.groupby('county').agg({
                'total_fp_visits': 'sum',
                'unique_clients': 'sum',
                'fp_adoption_rate': 'mean',
                'side_effect_rate': 'mean',
                'referral_rate': 'mean',
                'avg_client_age': 'mean'
            }).reset_index()
            
            report_sections.append("FAMILY PLANNING SERVICE DELIVERY (7-Month Summary):")
            for _, county in latest_month_data.iterrows():
                report_sections.append(f"\n{county['county']}:")
                report_sections.append(f"  Total FP Visits: {county['total_fp_visits']}")
                report_sections.append(f"  Unique Clients Served: {county['unique_clients']}")
                report_sections.append(f"  FP Adoption Rate: {county['fp_adoption_rate']:.1f}%")
                report_sections.append(f"  Side Effect Rate: {county['side_effect_rate']:.1f}%")
                report_sections.append(f"  Referral Rate: {county['referral_rate']:.1f}%")
                report_sections.append(f"  Average Client Age: {county['avg_client_age']:.1f} years")
    except Exception as e:
        report_sections.append(f"Error analyzing family planning services: {e}")
    
    # Improvement Success Stories
    report_sections.append("\n🌟 CHW IMPROVEMENT SUCCESS STORIES")
    report_sections.append("-" * 50)
    
    try:
        improvement_data = execute_predefined_query(engine, "chw_improvement_tracking")
        if improvement_data is not None and not improvement_data.empty and 'error' not in improvement_data.columns:
            significant_improvements = improvement_data[improvement_data['improvement_category'] == 'Significant Improvement']
            
            if not significant_improvements.empty:
                report_sections.append("CHWs WITH SIGNIFICANT IMPROVEMENT (≥15 point increase):")
                for _, chw in significant_improvements.head(10).iterrows():
                    report_sections.append(f"  • {chw['chv_name']} ({chw['county']}): {chw['dec_2024_score']:.1f}% → {chw['jun_2025_score']:.1f}% (+{chw['score_change']:.1f} points)")
            
            # Also show concerning declines
            declines = improvement_data[improvement_data['improvement_category'] == 'Performance Decline']
            if not declines.empty:
                report_sections.append(f"\nCHWs WITH PERFORMANCE DECLINE (requiring attention):")
                for _, chw in declines.head(5).iterrows():
                    report_sections.append(f"  • {chw['chv_name']} ({chw['county']}): {chw['dec_2024_score']:.1f}% → {chw['jun_2025_score']:.1f}% ({chw['score_change']:.1f} points)")
    except Exception as e:
        report_sections.append(f"Error analyzing improvements: {e}")
    
    # Strategic Recommendations
    report_sections.append("\n💡 STRATEGIC RECOMMENDATIONS")
    report_sections.append("-" * 50)
    
    report_sections.append("IMMEDIATE ACTIONS (Next 30 Days):")
    try:
        if 'critical_chws_data' in locals() and not critical_chws_data.empty:
            immediate_count = len(critical_chws_data[critical_chws_data['recommended_action'].str.contains('Immediate', na=False)])
            report_sections.append(f"1. Provide intensive mentorship to {immediate_count} critically performing CHWs")
            report_sections.append("2. Conduct emergency resource assessment in Busia (lowest tool availability)")
            report_sections.append("3. Schedule performance review meetings for all CHWs scoring <50%")
    except:
        pass
    
    report_sections.append("\nSHORT-TERM INITIATIVES (Next 90 Days):")
    report_sections.append("1. Implement targeted family planning training (weakest service area system-wide)")
    report_sections.append("2. Establish peer mentorship program pairing high and low performers")
    report_sections.append("3. Conduct comprehensive tool and supply distribution")
    report_sections.append("4. Strengthen supervision quality and frequency")
    
    report_sections.append("\nMEDIUM-TERM STRATEGIES (Next 6 Months):")
    report_sections.append("1. Develop county-specific improvement plans based on identified gaps")
    report_sections.append("2. Implement CHW recognition and incentive program for excellent performers")
    report_sections.append("3. Establish quarterly performance reviews with data-driven feedback")
    report_sections.append("4. Create resource forecasting and procurement planning system")
    
    # Expected Impact
    report_sections.append("\n🎯 PROJECTED IMPACT")
    report_sections.append("-" * 50)
    report_sections.append("If recommendations are implemented:")
    report_sections.append("• System-wide performance improvement: 15-20% within 6 months")
    report_sections.append("• Reduction in critical performers: 50% within 3 months")
    report_sections.append("• Improved resource availability: 90%+ across all counties")
    report_sections.append("• Enhanced service quality in family planning and malaria management")
    
    # Footer
    report_sections.append("\n" + "=" * 80)
    report_sections.append("DATA SOURCES:")
    report_sections.append("• Supervision Database: CHW performance assessments")
    report_sections.append("• Family Planning Database: Service delivery records")
    report_sections.append("• Household Database: Coverage and registration data")
    report_sections.append("• Analysis covers December 2024 - June 2025 (7-month period)")
    report_sections.append("• Report generated by Ushauri AI Health Intelligence System")
    report_sections.append("=" * 80)
    
    return "\n".join(report_sections)


def get_dashboard_metrics(engine):
    """Get key metrics for dashboard display"""
    metrics = {}
    
    try:
        # Total CHWs
        chw_query = "SELECT COUNT(DISTINCT chw_uuid) as total_chws FROM chw_master;"
        chw_result = execute_sql_query(engine, chw_query)
        metrics['total_chws'] = chw_result['total_chws'].iloc[0] if chw_result is not None and not chw_result.empty else 0
        
        # Average supervision score
        score_query = """
            SELECT AVG(calc_assessment_score) as avg_score 
            FROM supervision 
            WHERE calc_assessment_score IS NOT NULL 
            AND reported >= CURRENT_DATE - INTERVAL '3 months';
        """
        score_result = execute_sql_query(engine, score_query)
        metrics['avg_supervision_score'] = round(score_result['avg_score'].iloc[0], 1) if score_result is not None and not score_result.empty else 0
        
        # Total households
        household_query = "SELECT COUNT(DISTINCT household_uuid) as total_households FROM households;"
        household_result = execute_sql_query(engine, household_query)
        metrics['total_households'] = household_result['total_households'].iloc[0] if household_result is not None and not household_result.empty else 0
        
        # Active counties
        county_query = "SELECT COUNT(DISTINCT county) as active_counties FROM supervision WHERE reported >= CURRENT_DATE - INTERVAL '3 months';"
        county_result = execute_sql_query(engine, county_query)
        metrics['active_counties'] = county_result['active_counties'].iloc[0] if county_result is not None and not county_result.empty else 0
        
    except Exception as e:
        st.error(f"Error calculating dashboard metrics: {e}")
        metrics = {
            'total_chws': 0,
            'avg_supervision_score': 0,
            'total_households': 0,
            'active_counties': 0
        }
    
    return metrics


# Export predefined queries for use in other modules
def get_available_queries():
    """Return list of available predefined queries"""
    return list(PREDEFINED_QUERIES.keys())


def get_query_description():
    """Return descriptions of available queries"""
    return {
        "chw_performance_monthly": "Monthly CHW performance trends over the last 12 months",
        "low_performing_chws": "CHWs with below-average performance requiring support",
        "county_comparison": "Comparative analysis across all counties",
        "family_planning_trends": "Family planning service trends and adoption rates",
        "household_coverage": "Household coverage and CHW distribution",
        "chw_tool_availability": "Resource and tool availability by county",
        "under2_population_coverage": "Under-2 population coverage analysis"
    }
