# Check Frontend Logs in Railway

The frontend service crashed. Here's how to see what went wrong:

## Steps to View Logs

1. Go to Railway: https://railway.app/project/practical-dream
2. Click on the **frontend service** (heartfelt-benevolence)
3. Click on the **Logs** tab
4. Look for error messages

## Common Issues

### Issue 1: Port Not Listening
- Error: "Address already in use" or "Cannot bind to port"
- Solution: The nginx container needs to listen on the PORT environment variable

### Issue 2: Nginx Config Error
- Error: "nginx: [emerg] bind() to 0.0.0.0:80 failed"
- Solution: Check nginx.conf syntax

### Issue 3: Missing Files
- Error: "No such file or directory"
- Solution: Check Dockerfile COPY commands

## What to Do

1. Check the logs in Railway
2. Copy the error message
3. Tell me what you see

The most likely issue is that nginx is trying to listen on port 80, but Railway expects it to listen on the PORT environment variable (8080).

We may need to update the nginx.conf or Dockerfile to handle this.
