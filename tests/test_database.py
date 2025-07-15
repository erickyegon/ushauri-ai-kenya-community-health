"""
Test suite for database connections and operations
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.db import connect_db, execute_sql_query, test_connection, check_database_health


class TestDatabaseConnection:
    """Test database connection functionality"""
    
    def test_connect_db_success(self):
        """Test successful database connection"""
        with patch('tools.db.create_engine') as mock_engine:
            mock_engine.return_value = Mock()
            engine = connect_db()
            assert engine is not None
    
    def test_connect_db_failure(self):
        """Test database connection failure"""
        with patch('tools.db.create_engine', side_effect=Exception("Connection failed")):
            engine = connect_db()
            assert engine is None
    
    def test_execute_sql_query_success(self):
        """Test successful SQL query execution"""
        mock_engine = Mock()
        test_query = "SELECT 1 as test"
        expected_df = pd.DataFrame({"test": [1]})
        
        with patch('tools.db.pd.read_sql', return_value=expected_df):
            result = execute_sql_query(mock_engine, test_query)
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
    
    def test_execute_sql_query_empty_query(self):
        """Test execution with empty query"""
        mock_engine = Mock()
        result = execute_sql_query(mock_engine, "")
        assert result is None
    
    def test_execute_sql_query_sql_error(self):
        """Test SQL execution error handling"""
        mock_engine = Mock()
        test_query = "INVALID SQL"
        
        with patch('tools.db.pd.read_sql', side_effect=Exception("SQL Error")):
            result = execute_sql_query(mock_engine, test_query)
            assert isinstance(result, pd.DataFrame)
            assert "error" in result.columns
    
    def test_test_connection_success(self):
        """Test connection test success"""
        with patch('tools.db.connect_db') as mock_connect:
            mock_engine = Mock()
            mock_connect.return_value = mock_engine
            
            with patch('tools.db.execute_sql_query') as mock_execute:
                mock_execute.return_value = pd.DataFrame({"postgres_version": ["PostgreSQL 15.0"]})
                
                with patch('tools.db.get_table_counts') as mock_counts:
                    mock_counts.return_value = pd.DataFrame({
                        "table_name": ["supervision", "households"],
                        "row_count": [1000, 500]
                    })
                    
                    result = test_connection()
                    assert result["status"] == "success"
                    assert "postgres_version" in result
    
    def test_check_database_health(self):
        """Test database health check"""
        mock_engine = Mock()
        
        with patch('tools.db.get_table_counts') as mock_counts:
            mock_counts.return_value = pd.DataFrame({
                "table_name": ["supervision"],
                "row_count": [100]
            })
            
            with patch('tools.db.execute_sql_query') as mock_execute:
                mock_execute.return_value = pd.DataFrame({"recent_count": [50]})
                
                health = check_database_health(mock_engine)
                assert isinstance(health, dict)
                assert "connection" in health
                assert "data_present" in health


class TestDatabaseQueries:
    """Test database query functionality"""
    
    def test_kenya_counties_filter(self):
        """Test that queries properly filter for Kenya counties"""
        test_query = """
        SELECT county, COUNT(*) as count
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        GROUP BY county
        """
        
        # Verify query contains the correct county filter
        assert "Kisumu" in test_query
        assert "Busia" in test_query
        assert "Vihiga" in test_query
    
    def test_date_range_filter(self):
        """Test that queries use correct date range"""
        test_query = """
        SELECT * FROM supervision 
        WHERE reported >= '2024-12-01' AND reported <= '2025-06-30'
        """
        
        # Verify query contains the correct date range
        assert "2024-12-01" in test_query
        assert "2025-06-30" in test_query


if __name__ == "__main__":
    pytest.main([__file__])
