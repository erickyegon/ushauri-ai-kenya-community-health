# 🏗️ High-Level Design (HDL)
## Kenya Health AI System - System Architecture

**Version:** 1.0  
**Date:** July 2025  
**Status:** Active Development  
**Related:** [PRD](./PRD.md) | [LDL](./LDL.md)

---

## 🎯 Architecture Overview

The Kenya Health AI System serves as an **intelligent analytics layer** for Kenya's national e-CHIS (electronic Community Health Information System), following a **multi-agent microservices architecture** built on AutoGen 0.6+ framework. The system processes data from the national e-CHIS database containing information from 107,000 Community Health Promoters to provide county-level insights.

### Core Principles
1. **e-CHIS Integration**: Seamless integration with Kenya's national electronic Community Health Information System
2. **Agent-Driven Analytics**: Specialized AI agents handle specific health data analysis tasks
3. **County-Focused**: Designed to serve county health management teams with localized insights
4. **Scalable Architecture**: Handles data from 107K CHPs across Kenya's 47 counties
5. **Government Alignment**: Supports Kenya Community Health Strategy 2020-2025 objectives

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
├─────────────────────────────────────────────────────────────┤
│  County Health │  Streamlit  │  REST APIs  │  Dashboards   │
│  Dashboards    │     UI      │             │               │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                         │
├─────────────────────────────────────────────────────────────┤
│           AutoGen Multi-Agent System (e-CHIS Analytics)     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐│
│  │SQL Generator│ │CHP Analysis │ │Visualization│ │ Memory  ││
│  │   Agent     │ │   Agent     │ │   Agent     │ │ Agent   ││
│  │(e-CHIS Data)│ │(107K CHPs)  │ │(County View)│ │         ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘│
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                            │
├─────────────────────────────────────────────────────────────┤
│e-CHIS Sync│County Analytics│Report Gen│Vector Search│County Auth│
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
├─────────────────────────────────────────────────────────────┤
│Local PostgreSQL│  Vector DB  │County Cache │ e-CHIS Mirror │
│(County Data)   │             │(Redis)      │               │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                 EXTERNAL SERVICES                           │
├─────────────────────────────────────────────────────────────┤
│National e-CHIS │ Groq API    │ HuggingFace │   Monitoring   │
│Database        │             │             │               │
└─────────────────────────────────────────────────────────────┘
```

## 🤖 Multi-Agent Architecture

### Agent Orchestration
The system uses **AutoGen 0.6+ RoundRobinGroupChat** for agent coordination:

```python
# Agent Workflow Example
User Query → SQL Generator → SQL Executor → Analysis Agent → Visualization Agent → Response
```

### Agent Specifications

#### 1. 🔍 SQL Generator Agent
**Purpose**: Convert natural language queries to SQL
- **Input**: Natural language questions about CHW data
- **Output**: Validated SQL queries
- **LLM**: Groq llama-3.1-8b-instant (Primary)
- **Fallback**: HuggingFace models
- **Specialization**: Kenya health data schema expertise

#### 2. 📊 Analysis Agent
**Purpose**: Perform statistical analysis and insights
- **Input**: Query results and analysis requirements
- **Output**: Statistical insights, trends, recommendations
- **Capabilities**: Descriptive stats, trend analysis, comparisons
- **Domain**: Kenya health system KPIs and metrics

#### 3. 📈 Visualization Agent
**Purpose**: Create charts and visual representations
- **Input**: Analysis results and visualization requirements
- **Output**: Plotly charts, tables, dashboards
- **Chart Types**: Bar, line, scatter, heatmaps, geographic maps
- **Responsive**: Mobile and desktop optimized

#### 4. 🧠 Memory Agent
**Purpose**: Maintain conversation context and learning
- **Input**: Conversation history, user preferences
- **Output**: Context-aware responses, personalized suggestions
- **Storage**: Vector embeddings for semantic search
- **Learning**: Continuous improvement from user interactions

## 🔄 Data Flow Architecture

### 1. Query Processing Flow
```
User Input → NLP Processing → Intent Recognition → Agent Selection → 
SQL Generation → Query Validation → Execution → Analysis → 
Visualization → Response Formatting → User Interface
```

### 2. Real-Time Analytics Flow
```
Database Changes → Event Triggers → Stream Processing → 
Agent Analysis → Dashboard Updates → Alert Generation → 
Notification Delivery
```

### 3. Batch Processing Flow
```
Scheduled Jobs → Data Extraction → Batch Analysis → 
Report Generation → Distribution → Archive Storage
```

## 🗄️ Data Architecture

### Database Design
- **Primary DB**: PostgreSQL 14+ with vector extensions
- **Schema**: Optimized for CHW performance data
- **Partitioning**: By county and date for performance
- **Indexing**: Composite indexes on frequently queried columns

### Data Sources
1. **CHW Performance Data**: Supervision records, assessments
2. **Geographic Data**: County boundaries, facility locations
3. **Health Indicators**: Family planning, immunization, etc.
4. **User Data**: Preferences, query history, permissions

### Data Processing Pipeline
```
Raw Data → Validation → Transformation → Enrichment → 
Storage → Indexing → Vector Embedding → Search Index
```

## 🔧 Technology Stack

### Core Technologies
- **Runtime**: Python 3.10+
- **Framework**: FastAPI (APIs), Streamlit (UI)
- **AI/ML**: AutoGen 0.6+, LangChain, sentence-transformers
- **Database**: PostgreSQL 14+, pgvector extension
- **Caching**: Redis for session and query caching
- **Search**: FAISS for vector similarity search

### External APIs
- **Primary LLM**: Groq API (llama-3.1-8b-instant)
- **Backup LLM**: HuggingFace Inference API
- **Monitoring**: Custom health checks and metrics
- **Notifications**: SMTP for email alerts

### Infrastructure
- **Containerization**: Docker with multi-stage builds
- **Orchestration**: Docker Compose (current), Kubernetes (future)
- **Load Balancing**: Nginx (future)
- **Monitoring**: Prometheus + Grafana (future)

## 🔐 Security Architecture

### Authentication & Authorization
- **Authentication**: JWT-based session management
- **Authorization**: Role-based access control (RBAC)
- **Roles**: Admin, Supervisor, Analyst, Viewer
- **Permissions**: Granular permissions per county/facility

### Data Security
- **Encryption**: AES-256 at rest, TLS 1.3 in transit
- **Data Masking**: PII protection in logs and exports
- **Audit Trail**: Complete logging of data access
- **Backup**: Encrypted daily backups with retention policy

### API Security
- **Rate Limiting**: Per-user and per-endpoint limits
- **Input Validation**: Comprehensive input sanitization
- **SQL Injection**: Parameterized queries and ORM protection
- **CORS**: Configured for specific domains only

## 📈 Scalability Design

### Horizontal Scaling
- **Stateless Services**: All services designed to be stateless
- **Load Distribution**: Round-robin load balancing
- **Database Scaling**: Read replicas for query distribution
- **Caching Strategy**: Multi-level caching (application, database, CDN)

### Performance Optimization
- **Query Optimization**: Indexed queries with execution plan analysis
- **Connection Pooling**: Database connection pooling
- **Async Processing**: Non-blocking I/O for API calls
- **Resource Management**: Memory and CPU optimization

### Monitoring & Observability
- **Health Checks**: Endpoint health monitoring
- **Metrics Collection**: Custom metrics for business KPIs
- **Logging**: Structured logging with correlation IDs
- **Alerting**: Automated alerts for system anomalies

## 🔄 Integration Architecture

### Internal Integrations
- **Agent Communication**: Message passing via AutoGen framework
- **Service Communication**: RESTful APIs with JSON payloads
- **Database Access**: SQLAlchemy ORM with connection pooling
- **Cache Integration**: Redis for distributed caching

### External Integrations
- **LLM APIs**: Groq and HuggingFace with fallback mechanisms
- **Email Service**: SMTP integration for notifications
- **File Storage**: Local filesystem with cloud migration path
- **Monitoring**: Health check endpoints for external monitoring

## 🚀 Deployment Architecture

### Environment Strategy
- **Development**: Local Docker Compose setup
- **Staging**: Cloud-based staging environment
- **Production**: High-availability cloud deployment
- **DR**: Disaster recovery with automated failover

### CI/CD Pipeline
```
Code Commit → Automated Tests → Security Scan → 
Build Docker Images → Deploy to Staging → 
Integration Tests → Deploy to Production → 
Health Checks → Monitoring
```

---

**Document Owner**: Kenya Health AI Architecture Team  
**Last Updated**: July 15, 2025  
**Next Review**: August 15, 2025  
**Related Documents**: [PRD](./PRD.md), [LDL](./LDL.md), [API Docs](./API.md)
