#!/usr/bin/env python3
"""
Cache Management Utility for Kenya Health AI
Provides cache statistics, cleanup, and management functions
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

try:
    from caching.enhanced_cache import get_enhanced_cache, get_cache_statistics
    from tools.memory import get_memory_statistics, cleanup_memory_system
    CACHING_AVAILABLE = True
except ImportError:
    CACHING_AVAILABLE = False

def display_cache_statistics():
    """Display comprehensive cache statistics"""
    print("📊 Cache System Statistics")
    print("=" * 50)
    
    if not CACHING_AVAILABLE:
        print("❌ Caching system not available")
        return
    
    try:
        # Enhanced cache statistics
        enhanced_stats = get_cache_statistics()
        print(f"🚀 Enhanced Cache:")
        print(f"   Total Entries: {enhanced_stats['total_entries']}")
        print(f"   Memory Usage: {enhanced_stats['total_size_mb']} MB ({enhanced_stats['memory_usage_percent']}%)")
        print(f"   Hit Rate: {enhanced_stats['hit_rate_percent']}%")
        print(f"   Cache Stats: {enhanced_stats['cache_stats']}")
        print()
        
        # Cache type breakdown
        if enhanced_stats['type_breakdown']:
            print("📈 Cache Type Breakdown:")
            for cache_type, count in enhanced_stats['type_breakdown'].items():
                print(f"   {cache_type}: {count} entries")
            print()
        
        # Memory system statistics
        memory_stats = get_memory_statistics()
        print(f"🧠 Memory System:")
        print(f"   Conversations: {memory_stats['conversations']['total_conversations']}")
        print(f"   Cache Hits: {memory_stats['cache']['total_hits']}")
        print(f"   Sessions: {memory_stats['conversations']['unique_sessions']}")
        print(f"   Recent Activity (24h): {memory_stats['conversations']['recent_24h']} queries")
        print()
        
        # Cache configurations
        print("⚙️  Cache Configurations:")
        for cache_type, config in enhanced_stats['cache_configs'].items():
            print(f"   {cache_type}: TTL={config['ttl']}s, Max={config['max_size']}")
        print()
        
    except Exception as e:
        print(f"❌ Error getting cache statistics: {e}")

def cleanup_cache_system():
    """Cleanup cache system"""
    print("🧹 Cleaning up cache system...")
    print("-" * 30)
    
    if not CACHING_AVAILABLE:
        print("❌ Caching system not available")
        return
    
    try:
        # Enhanced cache cleanup
        cache = get_enhanced_cache()
        expired_count = cache.clear_expired()
        print(f"✅ Cleared {expired_count} expired cache entries")
        
        # Memory system cleanup
        cleanup_result = cleanup_memory_system()
        if "error" not in cleanup_result:
            print(f"✅ Removed {cleanup_result['removed_conversations']} old conversations")
            print(f"✅ Removed {cleanup_result['removed_cache_entries']} old cache entries")
        else:
            print(f"❌ Memory cleanup error: {cleanup_result['error']}")
        
        # Vacuum and optimize
        cache.cleanup()
        print("✅ Cache database optimized")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

def export_cache_statistics():
    """Export cache statistics to JSON file"""
    if not CACHING_AVAILABLE:
        print("❌ Caching system not available")
        return
    
    try:
        # Gather all statistics
        enhanced_stats = get_cache_statistics()
        memory_stats = get_memory_statistics()
        
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'enhanced_cache': enhanced_stats,
            'memory_system': memory_stats
        }
        
        # Export to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cache_statistics_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"📁 Cache statistics exported to: {filename}")
        
    except Exception as e:
        print(f"❌ Error exporting statistics: {e}")

def test_cache_performance():
    """Test cache performance with sample operations"""
    print("🧪 Testing cache performance...")
    print("-" * 30)
    
    if not CACHING_AVAILABLE:
        print("❌ Caching system not available")
        return
    
    try:
        import time
        from caching.enhanced_cache import (
            cache_api_response, get_cached_api_response,
            cache_sql_query, get_cached_sql_query,
            cache_agent_response, get_cached_agent_response
        )
        
        # Test API response caching
        print("🌐 Testing API response caching...")
        test_endpoint = "test_endpoint"
        test_params = {"param1": "value1", "param2": "value2"}
        test_response = {"data": "test_response", "timestamp": time.time()}
        
        # Cache the response
        start_time = time.time()
        cache_api_response(test_endpoint, test_params, test_response)
        cache_time = time.time() - start_time
        print(f"   Cache write: {cache_time:.4f}s")
        
        # Retrieve from cache
        start_time = time.time()
        cached_response = get_cached_api_response(test_endpoint, test_params)
        retrieve_time = time.time() - start_time
        print(f"   Cache read: {retrieve_time:.4f}s")
        print(f"   Cache hit: {'✅' if cached_response else '❌'}")
        
        # Test SQL query caching
        print("🗄️  Testing SQL query caching...")
        test_query = "SELECT * FROM test_table WHERE id = 1"
        test_result = {"columns": ["id", "name"], "data": [[1, "test"]]}
        
        start_time = time.time()
        cache_sql_query(test_query, test_result)
        cache_time = time.time() - start_time
        print(f"   SQL cache write: {cache_time:.4f}s")
        
        start_time = time.time()
        cached_sql = get_cached_sql_query(test_query)
        retrieve_time = time.time() - start_time
        print(f"   SQL cache read: {retrieve_time:.4f}s")
        print(f"   SQL cache hit: {'✅' if cached_sql else '❌'}")
        
        # Test agent response caching
        print("🤖 Testing agent response caching...")
        test_agent_type = "test_agent"
        test_prompt = "What is the performance of CHWs in Kisumu?"
        test_agent_response = {"response": "Test agent response", "confidence": 0.95}
        
        start_time = time.time()
        cache_agent_response(test_agent_type, test_prompt, test_agent_response)
        cache_time = time.time() - start_time
        print(f"   Agent cache write: {cache_time:.4f}s")
        
        start_time = time.time()
        cached_agent = get_cached_agent_response(test_agent_type, test_prompt)
        retrieve_time = time.time() - start_time
        print(f"   Agent cache read: {retrieve_time:.4f}s")
        print(f"   Agent cache hit: {'✅' if cached_agent else '❌'}")
        
        print("✅ Cache performance test completed")
        
    except Exception as e:
        print(f"❌ Error during performance test: {e}")

def main():
    """Main cache management interface"""
    print("🏥 Kenya Health AI - Cache Management Utility")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("Usage: python cache_manager.py <command>")
        print()
        print("Available commands:")
        print("  stats     - Display cache statistics")
        print("  cleanup   - Clean up expired cache entries")
        print("  export    - Export cache statistics to JSON")
        print("  test      - Test cache performance")
        print("  all       - Run all operations")
        return
    
    command = sys.argv[1].lower()
    
    if command == "stats":
        display_cache_statistics()
    elif command == "cleanup":
        cleanup_cache_system()
    elif command == "export":
        export_cache_statistics()
    elif command == "test":
        test_cache_performance()
    elif command == "all":
        display_cache_statistics()
        print()
        test_cache_performance()
        print()
        cleanup_cache_system()
        print()
        export_cache_statistics()
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: stats, cleanup, export, test, all")

if __name__ == "__main__":
    main()
