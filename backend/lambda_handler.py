"""
AWS Lambda handler for the FastAPI application.
This wrapper allows the FastAPI app to run on AWS Lambda with API Gateway.
"""

from mangum import Mangum
from main import app

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

    # Process the request through Mangum
    response = handler(event, context)

    # Optional: Log response status
    logger.info(f"Response status: {response.get('statusCode', 'Unknown')}")

    return response