# Kenya Health AI System - Setup Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 12+ (optional for demo)
- Git

### 1. Environment Setup

```bash
# Clone and navigate to project
cd CHW

# Create and activate virtual environment
python -m venv chw_env
# Windows:
chw_env\Scripts\activate
# Linux/Mac:
source chw_env/bin/activate

# Install dependencies
pip install uv
uv pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# REQUIRED: Set at least one AI provider
```

### 3. AI Provider Setup (Choose ONE)

#### Option A: Hugging Face (RECOMMENDED)
```bash
# Get free API key from: https://huggingface.co/settings/tokens
# Add to .env:
HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### Option B: OpenAI
```bash
# Get API key from: https://platform.openai.com/api-keys
# Add to .env:
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### Option C: Local Ollama (Advanced)
```bash
# Install Ollama: https://ollama.ai
ollama pull llama3.2:3b
ollama serve
# No API key needed - auto-detected
```

### 4. Database Setup (Optional)

#### For Demo Mode:
- No database required
- Uses sample data and mock responses

#### For Production:
```bash
# Install PostgreSQL
# Create database
createdb kenya_health

# Update .env with your database credentials
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kenya_health
DB_USER=postgres
DB_PASSWORD=your_password
```

### 5. Run Application

```bash
# Start the application
streamlit run app/main_streamlit_app.py --server.port=8502

# Open browser to: http://localhost:8502
```

## 🧪 Testing

```bash
# Run test suite
python -m pytest tests/ -v

# Test specific components
python -m pytest tests/test_database.py -v
python -m pytest tests/test_agents.py -v
```

## 🎯 Usage Examples

### Basic Queries
- "Show CHW performance in Kisumu county"
- "Family planning trends in Busia"
- "Compare supervision scores across counties"

### Advanced Analytics
- "Which CHWs need additional training in malaria management?"
- "Identify resource gaps in Vihiga county"
- "Predict service delivery improvements needed"

## 🔧 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Reinstall dependencies
   uv pip install --force-reinstall -r requirements.txt
   ```

2. **API Key Issues**
   ```bash
   # Verify environment variables
   python -c "import os; print('HF_API_KEY:', bool(os.getenv('HF_API_KEY')))"
   ```

3. **Database Connection**
   ```bash
   # Test database connection
   python -c "from tools.db import connect_db; print('DB:', connect_db() is not None)"
   ```

### Demo Mode
If no API keys are configured, the system runs in demo mode with:
- Mock AI responses
- Sample data
- All features functional for testing

## 📊 System Architecture

```
CHW/
├── app/                 # Streamlit web interface
├── autogen_agents/      # AI agent system (AutoGen 0.6+)
├── tools/              # Database and utilities
├── tests/              # Test suite
├── data/               # Sample data and schemas
└── docs/               # Documentation
```

## 🔐 Security Notes

- Never commit `.env` files
- Use strong database passwords
- Rotate API keys regularly
- Enable SSL in production

## 📈 Performance Optimization

- Use connection pooling for database
- Enable caching for frequent queries
- Monitor API rate limits
- Scale horizontally with load balancers

## 🆘 Support

For issues or questions:
1. Check this guide
2. Review error logs
3. Test in demo mode
4. Contact system administrator

## 🎉 Success!

If you see the Streamlit interface at http://localhost:8502, you're ready to analyze Kenya health data!
