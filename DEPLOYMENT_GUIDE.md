# 🚀 Hugging Face Spaces Deployment Guide

## Step-by-Step Deployment to Hugging Face Spaces

### 1. **Prepare Your Repository**

1. **Create a new repository on Hugging Face Spaces:**
   - Go to https://huggingface.co/spaces
   - Click "Create new Space"
   - Choose a name like `ushauri-ai-kenya-health`
   - Select "Streamlit" as the SDK
   - Set visibility to "Public"

### 2. **Upload Files to Hugging Face Spaces**

Upload these key files to your Hugging Face Space:

```
📁 Your HF Space Repository/
├── app.py                    # Main entry point
├── requirements_hf.txt       # Dependencies
├── README_HF.md             # Space description (rename to README.md)
├── .env.demo                # Demo environment (rename to .env)
├── 📁 app/                  # Streamlit application
├── 📁 autogen_agents/       # AI agents
├── 📁 tools/                # Utilities including demo_db.py
├── 📁 memory/               # Memory storage
├── 📁 embeddings/           # Vector embeddings
└── 📁 reports/              # Report templates
```

### 3. **Configure Environment Variables**

In your Hugging Face Space settings, add these environment variables:

#### Required (for AI functionality):
```bash
GROQ_API_KEY=your_groq_api_key_here
HF_API_KEY=your_hugging_face_api_key_here
```

#### Optional (for enhanced features):
```bash
DEMO_MODE=true
USE_SAMPLE_DATA=true
STREAMLIT_SERVER_HEADLESS=true
```

### 4. **File Modifications for HF Spaces**

#### A. Rename files:
- `README_HF.md` → `README.md`
- `requirements_hf.txt` → `requirements.txt`
- `.env.demo` → `.env`

#### B. Update the main README.md with the HF Spaces header:
```yaml
---
title: Ushauri AI - Kenya Health Intelligence
emoji: 🇰🇪
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.28.0
app_file: app.py
pinned: false
license: mit
tags:
- healthcare
- kenya
- ai
- community-health
---
```

### 5. **Test Locally Before Deployment**

```bash
# Install dependencies
pip install -r requirements_hf.txt

# Set demo mode
export DEMO_MODE=true
export USE_SAMPLE_DATA=true

# Run locally
python app.py
```

### 6. **Deploy to Hugging Face Spaces**

#### Option A: Web Interface
1. Upload all files through the HF Spaces web interface
2. The space will automatically build and deploy

#### Option B: Git (Recommended)
```bash
# Clone your space
git clone https://huggingface.co/spaces/YOUR_USERNAME/ushauri-ai-kenya-health
cd ushauri-ai-kenya-health

# Copy files from your CHW directory
cp -r /path/to/CHW/* .

# Rename files for HF Spaces
mv README_HF.md README.md
mv requirements_hf.txt requirements.txt
mv .env.demo .env

# Commit and push
git add .
git commit -m "Deploy Ushauri AI - Kenya Health Intelligence System"
git push
```

### 7. **Configure Space Settings**

In your HF Space settings:

#### Hardware:
- **CPU**: Basic (free tier) or CPU upgrade for better performance
- **Storage**: Persistent storage for embeddings and memory

#### Environment Variables:
```bash
GROQ_API_KEY=your_actual_groq_key
HF_API_KEY=your_actual_hf_key
DEMO_MODE=true
USE_SAMPLE_DATA=true
```

#### Secrets (for sensitive data):
- Add API keys as secrets rather than environment variables

### 8. **Verify Deployment**

After deployment, check:

1. **Space loads successfully** ✅
2. **All tabs are accessible** ✅
3. **AI Assistant responds** ✅
4. **Reports generate** ✅
5. **Sample data displays** ✅

### 9. **Customize for Your Needs**

#### For Production Deployment:
1. **Replace demo database** with real PostgreSQL connection
2. **Update environment variables** for production
3. **Add authentication** if needed
4. **Configure proper logging**

#### For Demo/Showcase:
1. **Keep demo mode enabled**
2. **Add more sample data** in `tools/demo_db.py`
3. **Customize branding** in the Streamlit app
4. **Add usage instructions**

### 10. **Maintenance and Updates**

#### Regular Updates:
```bash
# Pull latest changes
git pull

# Update dependencies if needed
pip install -r requirements.txt --upgrade

# Test locally
python app.py

# Deploy updates
git add .
git commit -m "Update: [description]"
git push
```

#### Monitor Performance:
- Check HF Spaces logs for errors
- Monitor API usage (Groq/HF)
- Update sample data as needed

## 🔧 Troubleshooting

### Common Issues:

1. **Space won't start**:
   - Check requirements.txt for compatibility
   - Verify all files are uploaded
   - Check logs for specific errors

2. **AI not responding**:
   - Verify API keys are set correctly
   - Check Groq API quota
   - Ensure demo mode is enabled

3. **Database errors**:
   - Confirm demo_db.py is being used
   - Check DEMO_MODE environment variable

4. **Memory issues**:
   - Reduce sample data size
   - Optimize embeddings loading
   - Consider CPU upgrade

## 📞 Support

For deployment issues:
1. Check HF Spaces documentation
2. Review error logs in the space
3. Test locally first
4. Open an issue in the repository

## 🎯 Success Metrics

Your deployment is successful when:
- ✅ Space loads without errors
- ✅ All 5 tabs are functional
- ✅ AI Assistant generates responses
- ✅ Reports can be generated and downloaded
- ✅ Sample data displays correctly
- ✅ No critical errors in logs

**Ready to deploy? Follow the steps above and showcase Kenya's health intelligence system to the world! 🇰🇪**
