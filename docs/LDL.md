# 🔧 Low-Level Design (LDL)
## Kenya Health AI System - Technical Implementation Details

**Version:** 1.0  
**Date:** July 2025  
**Status:** Active Development  
**Related:** [PRD](./PRD.md) | [HDL](./HDL.md)

---

## 🗄️ Database Schema Design

### Core Tables

#### 1. CHP Performance Table (e-CHIS Mirror)
```sql
CREATE TABLE chp_performance (
    id SERIAL PRIMARY KEY,
    echis_chp_id VARCHAR(50) NOT NULL, -- e-CHIS CHP identifier
    chp_name VARCHAR(255) NOT NULL,
    county VARCHAR(100) NOT NULL,
    sub_county VARCHAR(255),
    ward VARCHAR(255),
    community_unit VARCHAR(255),
    facility_name VARCHAR(255),
    supervision_date DATE NOT NULL,
    echis_sync_timestamp TIMESTAMP, -- Last sync from e-CHIS

    -- Performance Scores from e-CHIS (0-100)
    calc_assessment_score DECIMAL(5,2),
    calc_family_planning_score DECIMAL(5,2),
    calc_immunization_score DECIMAL(5,2),
    calc_pneumonia_score DECIMAL(5,2),
    calc_diarrhea_score DECIMAL(5,2),
    calc_maternal_health_score DECIMAL(5,2),
    calc_nutrition_score DECIMAL(5,2),

    -- e-CHIS Integration Fields
    echis_record_id VARCHAR(100), -- Original e-CHIS record ID
    android_device_id VARCHAR(100), -- CHP's Android device
    data_quality_score DECIMAL(5,2), -- Data completeness from e-CHIS

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for 107K CHP data
    INDEX idx_county_date (county, supervision_date),
    INDEX idx_chp_performance (echis_chp_id, supervision_date),
    INDEX idx_scores (calc_assessment_score, calc_family_planning_score),
    INDEX idx_echis_sync (echis_sync_timestamp, county),
    UNIQUE INDEX idx_echis_record (echis_record_id)
);
```

#### 2. Query History Table
```sql
CREATE TABLE query_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    query_text TEXT NOT NULL,
    sql_generated TEXT,
    execution_time_ms INTEGER,
    result_count INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Vector embedding for similarity search
    embedding VECTOR(384),
    
    INDEX idx_user_queries (user_id, created_at),
    INDEX idx_embedding USING ivfflat (embedding vector_cosine_ops)
);
```

#### 3. User Sessions Table
```sql
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(100),
    county_access TEXT[], -- Array of accessible counties
    role VARCHAR(50) DEFAULT 'viewer',
    preferences JSONB,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    
    INDEX idx_session (session_id),
    INDEX idx_user_activity (user_id, last_activity)
);
```

## 🔗 e-CHIS Integration Architecture

### Data Synchronization from National e-CHIS
The system integrates with Kenya's national electronic Community Health Information System to access data from 107,000 Community Health Promoters.

#### 1. e-CHIS Data Pipeline
```python
class EchisDataSynchronizer:
    """Synchronizes data from national e-CHIS to local PostgreSQL"""

    def __init__(self, echis_connection, local_db):
        self.echis_connection = echis_connection
        self.local_db = local_db
        self.sync_batch_size = 1000  # Handle large CHP datasets

    async def sync_chp_performance_data(self, county_filter=None):
        """Sync CHP performance data from e-CHIS"""
        try:
            # Query e-CHIS for CHP data
            echis_query = self._build_echis_query(county_filter)
            echis_data = await self.echis_connection.execute(echis_query)

            # Transform e-CHIS data to local schema
            transformed_data = self._transform_echis_data(echis_data)

            # Batch insert to local PostgreSQL
            await self._batch_insert_chp_data(transformed_data)

            # Update sync timestamp
            await self._update_sync_metadata(county_filter)

        except Exception as e:
            logger.error(f"e-CHIS sync failed: {e}")
            raise

    def _build_echis_query(self, county_filter):
        """Build query for e-CHIS database"""
        base_query = """
        SELECT
            chp_id, chp_name, county, sub_county, ward,
            community_unit, facility_name, supervision_date,
            assessment_score, family_planning_score,
            immunization_score, pneumonia_score,
            android_device_id, data_collection_timestamp
        FROM echis_chp_performance
        WHERE supervision_date >= %s
        """

        if county_filter:
            base_query += " AND county IN %s"

        return base_query
```

### Data Sources Integration
1. **National e-CHIS Database**:
   - Primary data source with 107K CHP records
   - Android device data collection synchronized daily
   - Government-managed infrastructure

2. **County Health Management Systems**:
   - Local county-specific configurations
   - User access control by county
   - Performance benchmarking data

3. **Kenya Community Health Strategy Indicators**:
   - Aligned with 2020-2025 strategy objectives
   - Government-defined performance metrics
   - UHC (Universal Health Coverage) indicators

## 🤖 Agent Implementation Details

### 1. SQL Generator Agent

```python
class SQLGeneratorAgent:
    """Specialized agent for converting natural language to SQL"""
    
    def __init__(self, model_client, db_schema):
        self.model_client = model_client
        self.db_schema = db_schema
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return f"""
        You are a SQL expert for Kenya's e-CHIS (electronic Community Health Information System) data analysis.

        Context:
        - Data from Kenya's 107,000 Community Health Promoters (CHPs)
        - Supports Kenya Community Health Strategy 2020-2025
        - County-level analysis for health management teams
        - Data collected via Android devices and synchronized from national e-CHIS

        Database Schema:
        {self.db_schema}

        Available Counties: Kisumu, Busia, Vihiga (pilot counties)
        Date Range: 2024-12-01 to 2025-06-30
        CHP Scale: Data represents subset of 107K national CHPs

        Rules:
        1. Always use parameterized queries for security
        2. Include county filters when relevant for county health managers
        3. Use appropriate date ranges within e-CHIS data availability
        4. Validate column names against e-CHIS mirror schema
        5. Return only SELECT statements
        6. Consider CHP performance metrics aligned with government strategy
        7. Use echis_chp_id for CHP identification (not legacy chw_id)
        """
    
    async def generate_sql(self, user_query: str) -> SQLResult:
        """Generate SQL from natural language query"""
        try:
            # Prepare context with schema and examples
            context = self._prepare_context(user_query)
            
            # Call LLM with structured prompt
            response = await self.model_client.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # Parse and validate SQL
            sql_query = self._extract_sql(response.content)
            validation_result = self._validate_sql(sql_query)
            
            return SQLResult(
                query=sql_query,
                valid=validation_result.valid,
                error=validation_result.error,
                estimated_rows=validation_result.estimated_rows
            )
            
        except Exception as e:
            return SQLResult(valid=False, error=str(e))
    
    def _validate_sql(self, sql: str) -> ValidationResult:
        """Validate SQL query against schema and security rules"""
        # Implementation details for SQL validation
        pass
```

### 2. Analysis Agent

```python
class AnalysisAgent:
    """Agent for statistical analysis and insights generation"""
    
    def __init__(self, model_client):
        self.model_client = model_client
        self.analysis_functions = {
            'descriptive_stats': self._descriptive_statistics,
            'trend_analysis': self._trend_analysis,
            'comparative_analysis': self._comparative_analysis,
            'performance_insights': self._performance_insights
        }
    
    async def analyze_data(self, data: pd.DataFrame, analysis_type: str) -> AnalysisResult:
        """Perform analysis on query results"""
        try:
            # Determine analysis type
            if analysis_type == 'auto':
                analysis_type = self._determine_analysis_type(data)
            
            # Perform analysis
            analysis_func = self.analysis_functions.get(analysis_type)
            if not analysis_func:
                raise ValueError(f"Unknown analysis type: {analysis_type}")
            
            results = analysis_func(data)
            
            # Generate insights using LLM
            insights = await self._generate_insights(data, results)
            
            return AnalysisResult(
                analysis_type=analysis_type,
                results=results,
                insights=insights,
                recommendations=await self._generate_recommendations(results)
            )
            
        except Exception as e:
            return AnalysisResult(error=str(e))
    
    def _descriptive_statistics(self, data: pd.DataFrame) -> Dict:
        """Calculate descriptive statistics"""
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        stats = {}
        
        for col in numeric_cols:
            stats[col] = {
                'mean': data[col].mean(),
                'median': data[col].median(),
                'std': data[col].std(),
                'min': data[col].min(),
                'max': data[col].max(),
                'count': data[col].count()
            }
        
        return stats
```

### 3. Visualization Agent

```python
class VisualizationAgent:
    """Agent for creating charts and visualizations"""
    
    def __init__(self, model_client):
        self.model_client = model_client
        self.chart_types = {
            'bar': self._create_bar_chart,
            'line': self._create_line_chart,
            'scatter': self._create_scatter_plot,
            'heatmap': self._create_heatmap,
            'geographic': self._create_geographic_map
        }
    
    async def create_visualization(self, data: pd.DataFrame, viz_request: str) -> VisualizationResult:
        """Create appropriate visualization for data"""
        try:
            # Determine best chart type
            chart_type = await self._determine_chart_type(data, viz_request)
            
            # Create visualization
            chart_func = self.chart_types.get(chart_type)
            if not chart_func:
                chart_type = 'bar'  # Default fallback
                chart_func = self.chart_types['bar']
            
            figure = chart_func(data, viz_request)
            
            return VisualizationResult(
                chart_type=chart_type,
                figure=figure,
                description=await self._generate_chart_description(data, figure)
            )
            
        except Exception as e:
            return VisualizationResult(error=str(e))
    
    def _create_bar_chart(self, data: pd.DataFrame, request: str) -> go.Figure:
        """Create bar chart with automatic column selection"""
        # Determine x and y columns
        categorical_cols = data.select_dtypes(include=['object']).columns
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        
        x_col = categorical_cols[0] if len(categorical_cols) > 0 else data.columns[0]
        y_col = numeric_cols[0] if len(numeric_cols) > 0 else data.columns[1]
        
        fig = px.bar(
            data, 
            x=x_col, 
            y=y_col,
            title=f"{y_col} by {x_col}",
            color=x_col if len(data[x_col].unique()) <= 10 else None
        )
        
        fig.update_layout(
            xaxis_title=x_col.replace('_', ' ').title(),
            yaxis_title=y_col.replace('_', ' ').title(),
            showlegend=True
        )
        
        return fig
```

## 🔌 API Design

### REST API Endpoints

#### 1. Query Processing API
```python
@app.post("/api/v1/query")
async def process_query(request: QueryRequest) -> QueryResponse:
    """Process natural language query and return results"""
    
    # Input validation
    if not request.query or len(request.query.strip()) < 3:
        raise HTTPException(400, "Query too short")
    
    # Rate limiting check
    await check_rate_limit(request.user_id)
    
    # Process query through agent system
    result = await group_chat_processor.process_query(
        query=request.query,
        user_id=request.user_id,
        county_filter=request.county_filter
    )
    
    # Log query for analytics
    await log_query(request, result)
    
    return QueryResponse(
        success=result.success,
        data=result.data,
        visualization=result.visualization,
        insights=result.insights,
        execution_time=result.execution_time
    )

# Request/Response Models
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    user_id: str
    county_filter: Optional[List[str]] = None
    analysis_type: Optional[str] = "auto"

class QueryResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    visualization: Optional[Dict] = None
    insights: Optional[List[str]] = None
    execution_time: float
    error: Optional[str] = None
```

#### 2. Dashboard API
```python
@app.get("/api/v1/dashboard/metrics")
async def get_dashboard_metrics(
    county: Optional[str] = None,
    date_range: Optional[str] = "30d"
) -> DashboardMetrics:
    """Get real-time dashboard metrics"""
    
    # Build query based on filters
    query_builder = DashboardQueryBuilder()
    query = query_builder.build_metrics_query(county, date_range)
    
    # Execute query
    results = await db.execute(query)
    
    # Calculate metrics
    metrics = MetricsCalculator.calculate(results)
    
    return DashboardMetrics(
        total_chws=metrics.total_chws,
        avg_performance=metrics.avg_performance,
        county_breakdown=metrics.county_breakdown,
        trend_data=metrics.trend_data,
        last_updated=datetime.utcnow()
    )
```

## 🔧 Configuration Management

### Environment Configuration
```python
class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "kenya_health"
    db_user: str
    db_password: str
    
    # AI APIs
    groq_api_key: str
    hf_api_key: str
    
    # Application
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # Security
    secret_key: str
    session_timeout: int = 3600
    
    # Performance
    max_query_time: int = 30
    cache_ttl: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Usage
settings = Settings()
```

## 🧪 Testing Strategy

### Unit Tests
```python
class TestSQLGeneratorAgent:
    """Test cases for SQL Generator Agent"""
    
    @pytest.fixture
    def agent(self):
        return SQLGeneratorAgent(mock_client, test_schema)
    
    @pytest.mark.asyncio
    async def test_simple_query_generation(self, agent):
        """Test basic query generation"""
        query = "Show all CHWs from Kisumu"
        result = await agent.generate_sql(query)
        
        assert result.valid
        assert "SELECT" in result.query.upper()
        assert "kisumu" in result.query.lower()
        assert "chw" in result.query.lower()
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, agent):
        """Test SQL injection prevention"""
        malicious_query = "Show CHWs; DROP TABLE chw_performance;"
        result = await agent.generate_sql(malicious_query)
        
        assert not result.valid or "DROP" not in result.query.upper()
```

### Integration Tests
```python
class TestEndToEndWorkflow:
    """Test complete query processing workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_query_workflow(self):
        """Test full query processing pipeline"""
        # Setup test data
        await setup_test_data()
        
        # Process query
        response = await client.post("/api/v1/query", json={
            "query": "Compare CHW performance between counties",
            "user_id": "test_user"
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert "data" in data
        assert "visualization" in data
```

---

**Document Owner**: Kenya Health AI Development Team  
**Last Updated**: July 15, 2025  
**Next Review**: August 15, 2025  
**Related Documents**: [PRD](./PRD.md), [HDL](./HDL.md), [API Docs](./API.md)
