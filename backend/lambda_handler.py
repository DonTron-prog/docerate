"""
AWS Lambda handler for the FastAPI application.
This wrapper allows the FastAPI app to run on AWS Lambda with API Gateway.
"""

from mangum import Mangum

try:
    from backend.main import app  # Lambda package includes backend/ directory
except ModuleNotFoundError as exc:  # pragma: no cover - local execution fallback
    if exc.name in {"backend", "backend.main"}:
        from main import app  # type: ignore
    else:
        raise

# Create the Lambda handler
handler = Mangum(app)

# Optional: Add Lambda-specific initialization
def lambda_handler(event, context):
    """
    AWS Lambda handler function.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        API Gateway response
    """
    # Optional: Add CloudWatch logging
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Log the incoming event for debugging (be careful with sensitive data)
    logger.info(f"Received event: {event.get('httpMethod', 'Unknown')} {event.get('path', 'Unknown')}")

    # Handle OPTIONS requests directly (CORS preflight)
    # API Gateway v2 HTTP API should handle this, but as fallback we handle it here
    if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS' or event.get('httpMethod') == 'OPTIONS':
        logger.info("Handling OPTIONS request directly")
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Max-Age': '3600'
            },
            'body': ''
        }

    # Process the request through Mangum
    response = handler(event, context)

    # Optional: Log response status
    logger.info(f"Response status: {response.get('statusCode', 'Unknown')}")

    return response
