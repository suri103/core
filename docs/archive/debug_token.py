import jwt
import json

# Decode the token without verification to see what's in it
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDEiLCJyb2xlIjoiYWRtaW4iLCJwcmFjdGljZV9pZCI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImV4cCI6MTc3NjMzMTIwNywidHlwZSI6InJlZnJlc2gifQ.0hzFXXdJwypufF3k_qVB5vhes6hg91CDl2OyXFQyJ2k"

# Decode without verification
decoded = jwt.decode(token, options={"verify_signature": False})
print("Token payload:")
print(json.dumps(decoded, indent=2))

# Check the user ID format
user_id = decoded.get("sub")
print(f"\nUser ID from token: {user_id}")
print(f"User ID type: {type(user_id)}")

# Check if it's a valid UUID format
import uuid
try:
    uuid_obj = uuid.UUID(user_id)
    print(f"Valid UUID: {uuid_obj}")
    print(f"UUID bytes: {uuid_obj.bytes}")
    print(f"UUID hex: {uuid_obj.hex}")
except Exception as e:
    print(f"Invalid UUID: {e}")