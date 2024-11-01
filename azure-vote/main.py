from flask import Flask, request, render_template
import os
import redis
import socket
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure import metrics_exporter
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer

# Azure Instrumentation Key
instrumentation_key = os.getenv('INSTRUMENTATION_KEY', 'e1927438-a67f-4261-bc7e-bd60c06846fa')

# Initialize Flask application
app = Flask(__name__)

# Configure logging with Azure Log Handler
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = AzureLogHandler(connection_string=f'InstrumentationKey={instrumentation_key}')
logger.addHandler(handler)

# Set up metrics exporter for application insights
metrics_exporter_instance = metrics_exporter.new_metrics_exporter(
    enable_standard_metrics=True,
    connection_string=f'InstrumentationKey={instrumentation_key}'
)

# Configure tracing with Azure
tracer = Tracer(
    exporter=AzureExporter(connection_string=f'InstrumentationKey={instrumentation_key}'),
    sampler=ProbabilitySampler(rate=1.0),
)

# Middleware for OpenCensus
FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string=f'InstrumentationKey={instrumentation_key}'),
    sampler=ProbabilitySampler(rate=1.0),
)

# Load configuration from a file or environment variables
app.config.from_pyfile('config_file.cfg')

# Read values for buttons and title from environment variables or config
button1 = os.getenv('VOTE1VALUE', app.config['VOTE1VALUE'])
button2 = os.getenv('VOTE2VALUE', app.config['VOTE2VALUE'])
title = os.getenv('TITLE', app.config['TITLE'])

# Initialize Redis connection
redis_client = redis.Redis()

# Set hostname as title for NLB demo if configured
if app.config.get('SHOWHOST') == "true":
    title = socket.gethostname()

# Initialize Redis keys for voting buttons if not already set
if not redis_client.get(button1): 
    redis_client.set(button1, 0)
if not redis_client.get(button2): 
    redis_client.set(button2, 0)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        # Fetch current vote counts
        vote1 = redis_client.get(button1).decode('utf-8')
        vote2 = redis_client.get(button2).decode('utf-8')

        # Trace votes
        with tracer.span(name="Cats_vote"):
            pass  # Add any specific tracing logic if needed
        
        with tracer.span(name="Dogs_vote"):
            pass  # Add any specific tracing logic if needed

        # Render the template with current votes
        return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

    elif request.method == 'POST':
        if request.form['vote'] == 'reset':
            # Reset vote counts
            redis_client.set(button1, 0)
            redis_client.set(button2, 0)

            # Log reset votes
            vote1 = redis_client.get(button1).decode('utf-8')
            logger.info('Cat vote reset', extra={'custom_dimensions': {'Cats Vote': vote1}})
            vote2 = redis_client.get(button2).decode('utf-8')
            logger.info('Dog vote reset', extra={'custom_dimensions': {'Dogs Vote': vote2}})

            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)
        else:
            # Increment the vote count
            vote = request.form['vote']
            redis_client.incr(vote, 1)

            # Fetch updated vote counts
            vote1 = redis_client.get(button1).decode('utf-8')
            vote2 = redis_client.get(button2).decode('utf-8')

            # Return updated results
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

if __name__ == "__main__":
    app.run(debug=True)  # Use debug=True for local development
    # app.run(host='0.0.0.0', threaded=True)  # Uncomment for deployment
