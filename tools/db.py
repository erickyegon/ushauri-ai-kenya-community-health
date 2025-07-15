"""
tools/db.py - PostgreSQL Database Connection and Query Execution
"""

import os
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st
from contextlib import contextmanager
import logging
import time

# Import performance monitoring
try:
    from monitoring.performance_monitor import record_performance_metric
except ImportError:
    # Fallback if monitoring module not available
    def record_performance_metric(metric_name: str, value: float, unit: str = 'seconds', metadata=None):
        pass

# Import enhanced caching
try:
    from caching.enhanced_cache import get_cached_sql_query, cache_sql_query
except ImportError:
    # Fallback if caching module not available
    def get_cached_sql_query(query: str): return None
    def cache_sql_query(query: str, result, ttl_seconds: int = 1800): pass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_config():
    """Get database configuration from environment variables or defaults"""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "kenya"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "Floridah2025!")
    }


@st.cache_resource
def connect_db():
    """
    Create and cache database connection using SQLAlchemy
    Returns engine object for database operations
    """
    config = get_db_config()
    
    try:
        # Create connection string
        connection_string = (
            f"postgresql+psycopg2://{config['user']}:{config['password']}@"
            f"{config['host']}:{config['port']}/{config['database']}"
        )
        
        # Create engine with connection pooling
        engine = create_engine(
            connection_string,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False  # Set to True for SQL query logging
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection established successfully")
        
        return engine
        
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        st.error(f"Failed to connect to database: {str(e)}")
        return None


def execute_sql_query(engine, query, params=None):
    """
    Execute SQL query and return results as pandas DataFrame
    
    Args:
        engine: SQLAlchemy engine object
        query: SQL query string
        params: Optional parameters for parameterized queries
    
    Returns:
        pandas.DataFrame or None if error
    """
    if engine is None:
        logger.error("No database engine provided")
        return None
    
    try:
        # Clean and validate query
        query = query.strip()
        if not query:
            logger.error("Empty query provided")
            return None

        # Check cache first (only for SELECT queries without parameters)
        if query.upper().startswith('SELECT') and not params:
            cached_result = get_cached_sql_query(query)
            if cached_result is not None:
                logger.info(f"Using cached query result for: {query[:50]}...")
                return cached_result

        # Start timing
        start_time = time.time()

        # Execute query with pandas
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

            # Record performance metric
            execution_time = time.time() - start_time
            record_performance_metric('database_query_time', execution_time, 'seconds', {
                'query_length': len(query),
                'result_rows': len(df),
                'result_columns': len(df.columns) if df is not None else 0,
                'has_params': params is not None,
                'cached': False
            })

            # Cache the result (only for SELECT queries without parameters)
            if query.upper().startswith('SELECT') and not params and df is not None:
                cache_sql_query(query, df, ttl_seconds=1800)  # Cache for 30 minutes
                logger.info(f"Cached query result for: {query[:50]}...")

            logger.info(f"Query executed successfully, returned {len(df)} rows in {execution_time:.3f}s")
            return df
            
    except SQLAlchemyError as e:
        logger.error(f"SQL execution error: {str(e)}")
        return pd.DataFrame({"error": [f"SQL Error: {str(e)}"]})
    
    except Exception as e:
        logger.error(f"Unexpected error during query execution: {str(e)}")
        return pd.DataFrame({"error": [f"Execution Error: {str(e)}"]})


def get_table_info(engine):
    """
    Get information about all tables in the database
    
    Returns:
        dict: Table names and their column information
    """
    if engine is None:
        return {}
    
    try:
        # Get table names
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
        """
        
        tables_df = execute_sql_query(engine, tables_query)
        if tables_df is None or 'error' in tables_df.columns:
            return {}
        
        table_info = {}
        
        for table_name in tables_df['table_name']:
            # Get column information for each table
            columns_query = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            AND table_schema = 'public'
            ORDER BY ordinal_position;
            """
            
            columns_df = execute_sql_query(engine, columns_query)
            if columns_df is not None and 'error' not in columns_df.columns:
                table_info[table_name] = columns_df.to_dict('records')
        
        return table_info
        
    except Exception as e:
        logger.error(f"Error getting table info: {str(e)}")
        return {}


def get_sample_data(engine, table_name, limit=5):
    """
    Get sample data from a specific table
    
    Args:
        engine: SQLAlchemy engine
        table_name: Name of table to sample
        limit: Number of rows to return
    
    Returns:
        pandas.DataFrame
    """
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = f"SELECT * FROM {table_name} LIMIT {limit};"
        return execute_sql_query(engine, query)
    
    except Exception as e:
        logger.error(f"Error getting sample data from {table_name}: {str(e)}")
        return pd.DataFrame({"error": [f"Cannot sample {table_name}: {str(e)}"]})


def get_table_counts(engine):
    """
    Get row counts for all tables
    
    Returns:
        pandas.DataFrame with table names and row counts
    """
    if engine is None:
        return pd.DataFrame()
    
    try:
        table_info = get_table_info(engine)
        counts = []
        
        for table_name in table_info.keys():
            count_query = f"SELECT COUNT(*) as count FROM {table_name};"
            count_df = execute_sql_query(engine, count_query)
            if count_df is not None and 'error' not in count_df.columns:
                counts.append({
                    'table_name': table_name,
                    'row_count': count_df['count'].iloc[0]
                })
        
        return pd.DataFrame(counts).sort_values('row_count', ascending=False)
        
    except Exception as e:
        logger.error(f"Error getting table counts: {str(e)}")
        return pd.DataFrame({"error": [f"Cannot get table counts: {str(e)}"]})


def test_connection():
    """
    Test database connection and return status
    
    Returns:
        dict: Connection status and basic info
    """
    engine = connect_db()
    
    if engine is None:
        return {
            "status": "failed",
            "message": "Could not establish database connection"
        }
    
    try:
        # Test basic query
        test_df = execute_sql_query(engine, "SELECT version() as postgres_version;")
        
        if test_df is not None and 'error' not in test_df.columns:
            # Get database statistics
            table_counts = get_table_counts(engine)
            total_tables = len(table_counts)
            total_rows = table_counts['row_count'].sum() if not table_counts.empty else 0
            
            return {
                "status": "success",
                "message": "Database connection successful",
                "postgres_version": test_df['postgres_version'].iloc[0],
                "total_tables": total_tables,
                "total_rows": int(total_rows),
                "largest_table": table_counts.iloc[0]['table_name'] if not table_counts.empty else "None"
            }
        else:
            return {
                "status": "failed",
                "message": "Database connected but query failed"
            }
            
    except Exception as e:
        return {
            "status": "failed", 
            "message": f"Connection test failed: {str(e)}"
        }


@contextmanager
def get_db_session(engine):
    """
    Context manager for database sessions
    
    Usage:
        with get_db_session(engine) as session:
            result = session.execute(query)
    """
    if engine is None:
        raise ValueError("No database engine provided")
    
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()


def execute_batch_queries(engine, queries):
    """
    Execute multiple queries in a single transaction
    
    Args:
        engine: SQLAlchemy engine
        queries: List of SQL query strings
    
    Returns:
        list: Results from each query
    """
    if engine is None:
        return []
    
    results = []
    
    try:
        with engine.begin() as conn:  # Auto-commit transaction
            for query in queries:
                df = pd.read_sql(text(query), conn)
                results.append(df)
        
        logger.info(f"Executed {len(queries)} queries successfully")
        return results
        
    except Exception as e:
        logger.error(f"Batch query execution failed: {str(e)}")
        return [pd.DataFrame({"error": [f"Batch execution failed: {str(e)}"]}) for _ in queries]


def get_database_schema():
    """
    Get comprehensive database schema information
    
    Returns:
        dict: Complete schema with tables, columns, types, constraints
    """
    engine = connect_db()
    if engine is None:
        return {}
    
    schema_query = """
    SELECT 
        t.table_name,
        c.column_name,
        c.data_type,
        c.is_nullable,
        c.column_default,
        c.character_maximum_length,
        tc.constraint_type,
        kcu.constraint_name
    FROM information_schema.tables t
    LEFT JOIN information_schema.columns c 
        ON t.table_name = c.table_name 
        AND t.table_schema = c.table_schema
    LEFT JOIN information_schema.table_constraints tc 
        ON t.table_name = tc.table_name 
        AND t.table_schema = tc.table_schema
    LEFT JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
        AND c.column_name = kcu.column_name
    WHERE t.table_schema = 'public'
    ORDER BY t.table_name, c.ordinal_position;
    """
    
    try:
        schema_df = execute_sql_query(engine, schema_query)
        return schema_df.to_dict('records') if schema_df is not None else {}
    
    except Exception as e:
        logger.error(f"Error getting database schema: {str(e)}")
        return {}


# Database health check functions
def check_database_health_detailed(engine):
    """
    Perform comprehensive database health check
    
    Returns:
        dict: Health status and metrics
    """
    health_status = {
        "connection": False,
        "tables_accessible": False,
        "data_present": False,
        "recent_data": False,
        "metrics": {}
    }
    
    if engine is None:
        return health_status
    
    try:
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            health_status["connection"] = True
        
        # Check table accessibility
        table_counts = get_table_counts(engine)
        if not table_counts.empty and 'error' not in table_counts.columns:
            health_status["tables_accessible"] = True
            health_status["metrics"]["table_count"] = len(table_counts)
            health_status["metrics"]["total_rows"] = int(table_counts['row_count'].sum())
        
        # Check if data exists
        if health_status["metrics"].get("total_rows", 0) > 0:
            health_status["data_present"] = True
        
        # Check for recent data (last 30 days)
        recent_data_query = """
        SELECT COUNT(*) as recent_count
        FROM supervision 
        WHERE reported >= CURRENT_DATE - INTERVAL '30 days';
        """
        
        recent_df = execute_sql_query(engine, recent_data_query)
        if recent_df is not None and 'error' not in recent_df.columns:
            recent_count = recent_df['recent_count'].iloc[0]
            health_status["recent_data"] = recent_count > 0
            health_status["metrics"]["recent_records"] = int(recent_count)
    
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["error"] = str(e)
    
    return health_status


def get_dashboard_metrics():
    """Get basic dashboard metrics for the Streamlit app"""
    try:
        engine = connect_db()
        if not engine:
            return {
                "total_chws": 0,
                "total_supervisions": 0,
                "avg_score": 0,
                "counties": 0
            }

        # Get basic metrics
        query = """
            SELECT
                COUNT(DISTINCT chv_uuid) as total_chws,
                COUNT(*) as total_supervisions,
                ROUND(AVG(calc_assessment_score), 1) as avg_score,
                COUNT(DISTINCT county) as counties
            FROM supervision
            WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
              AND reported >= '2024-12-01'
              AND reported <= '2025-06-30'
              AND calc_assessment_score IS NOT NULL
        """

        result_df = execute_sql_query(engine, query)

        if result_df is not None and 'error' not in result_df.columns and not result_df.empty:
            row = result_df.iloc[0]
            return {
                "total_chws": int(row['total_chws']) if row['total_chws'] else 0,
                "total_supervisions": int(row['total_supervisions']) if row['total_supervisions'] else 0,
                "avg_score": float(row['avg_score']) if row['avg_score'] else 0,
                "counties": int(row['counties']) if row['counties'] else 0
            }
        else:
            return {
                "total_chws": 0,
                "total_supervisions": 0,
                "avg_score": 0,
                "counties": 0
            }

    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}")
        return {
            "total_chws": 0,
            "total_supervisions": 0,
            "avg_score": 0,
            "counties": 0
        }


def check_database_health():
    """Check database health without parameters for Streamlit app"""
    try:
        engine = connect_db()
        if not engine:
            return {"status": "error", "message": "Cannot connect to database"}

        # Use the existing health check function
        health_result = check_database_health_detailed(engine)

        if health_result.get("connection", False):
            return {"status": "healthy", "message": "Database connection successful"}
        else:
            return {"status": "error", "message": "Database health check failed"}

    except Exception as e:
        return {"status": "error", "message": f"Database health check failed: {e}"}
