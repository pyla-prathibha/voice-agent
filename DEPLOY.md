# Voice Agent Deployment Guide

This guide covers different deployment strategies for the Voice Agent system.

## Prerequisites

1. **API Keys**: Obtain API keys for:
   - Plivo (Auth ID and Token)
   - ElevenLabs (API Key)
   - OpenAI (API Key)

2. **Server Requirements**:
   - Python 3.8+
   - 1GB+ RAM
   - Port 80/443 access
   - SSL certificate (for production)

## Quick Local Development

```bash
# 1. Clone and setup
git clone https://github.com/pyla-prathibha/voice-agent.git
cd voice-agent
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run demo
python run_example.py
```

## Docker Deployment

### Single Container

```bash
# Build and run
docker build -t voice-agent .
docker run -p 8080:8080 --env-file .env voice-agent
```

### Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f voice-agent

# Stop services
docker-compose down
```

## Production Deployment

### 1. Server Setup (Ubuntu/Debian)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip nginx portaudio19-dev

# Install Python packages
pip3 install -r requirements.txt
```

### 2. Nginx Configuration

Create `/etc/nginx/sites-available/voice-agent`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Proxy to Voice Agent
    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
    
    # WebSocket support for audio streaming
    location /ws/ {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/voice-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Systemd Service

Create `/etc/systemd/system/voice-agent.service`:

```ini
[Unit]
Description=Voice Agent Service
After=network.target

[Service]
Type=simple
User=voiceagent
WorkingDirectory=/opt/voice-agent
Environment=PATH=/opt/voice-agent/venv/bin
ExecStart=/opt/voice-agent/venv/bin/python main.py
Restart=always
RestartSec=10

# Environment variables
EnvironmentFile=/opt/voice-agent/.env

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/voice-agent/logs

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable voice-agent
sudo systemctl start voice-agent
sudo systemctl status voice-agent
```

### 4. Plivo Configuration

In your Plivo console, configure your application:

1. **Answer URL**: `https://your-domain.com/plivo/answer`
2. **Hangup URL**: `https://your-domain.com/plivo/hangup`
3. **Method**: POST

## Cloud Deployment

### AWS EC2

1. **Launch EC2 instance** (t3.small or larger)
2. **Security Group**: Allow ports 22, 80, 443
3. **Elastic IP**: Assign static IP
4. **Route 53**: Setup domain DNS
5. **Certificate Manager**: Get SSL certificate
6. **Load Balancer**: Optional for multiple instances

### Google Cloud Platform

```bash
# Deploy to Cloud Run
gcloud run deploy voice-agent \
  --image gcr.io/PROJECT_ID/voice-agent \
  --platform managed \
  --region us-central1 \
  --port 8080 \
  --set-env-vars PLIVO_AUTH_ID=xxx,ELEVENLABS_API_KEY=xxx
```

### Heroku

```bash
# Create Heroku app
heroku create your-voice-agent

# Set environment variables
heroku config:set PLIVO_AUTH_ID=xxx
heroku config:set PLIVO_AUTH_TOKEN=xxx
heroku config:set ELEVENLABS_API_KEY=xxx
heroku config:set OPENAI_API_KEY=xxx

# Deploy
git push heroku main
```

## Kubernetes Deployment

```yaml
# voice-agent-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voice-agent
  template:
    metadata:
      labels:
        app: voice-agent
    spec:
      containers:
      - name: voice-agent
        image: voice-agent:latest
        ports:
        - containerPort: 8080
        env:
        - name: PLIVO_AUTH_ID
          valueFrom:
            secretKeyRef:
              name: voice-agent-secrets
              key: plivo-auth-id
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: voice-agent-service
spec:
  selector:
    app: voice-agent
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

Deploy:
```bash
kubectl apply -f voice-agent-deployment.yaml
```

## Monitoring and Logging

### Health Checks

The system provides a health endpoint at `/health`:

```bash
curl http://your-domain.com/health
```

### Logging

Logs are structured and can be sent to various systems:

```python
# Configure structured logging
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
```

### Metrics

Monitor key metrics:
- Active call sessions
- Response times
- Error rates
- API usage

## Security Considerations

1. **Environment Variables**: Never commit API keys
2. **HTTPS**: Always use SSL in production
3. **Firewall**: Restrict access to necessary ports
4. **Rate Limiting**: Implement request rate limiting
5. **Monitoring**: Setup alerts for unusual activity

## Scaling

### Horizontal Scaling

1. **Load Balancer**: Distribute traffic across instances
2. **Session Affinity**: Ensure calls stick to same instance
3. **Shared State**: Use Redis for shared session data

### Vertical Scaling

- **CPU**: More cores for concurrent processing
- **Memory**: Larger memory for audio buffering
- **Network**: Higher bandwidth for audio streaming

## Troubleshooting

### Common Issues

1. **Audio Quality**: Check sample rates and codecs
2. **WebSocket Issues**: Verify proxy configuration
3. **API Timeouts**: Increase timeout values
4. **Memory Leaks**: Monitor memory usage

### Debug Mode

```bash
export LOG_LEVEL=DEBUG
python main.py
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Test API connection (if implemented)
curl -X POST http://localhost:8080/test/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

## Backup and Recovery

1. **Configuration**: Backup .env and config files
2. **Logs**: Archive conversation logs
3. **Monitoring**: Setup automated backups
4. **Recovery**: Document recovery procedures

## Performance Optimization

1. **Caching**: Cache TTS responses for common phrases
2. **CDN**: Use CDN for static assets
3. **Database**: Use database for conversation history
4. **Queue**: Implement job queues for heavy processing

For more detailed deployment assistance, please refer to the main README.md or create an issue in the repository.