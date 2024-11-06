from flask import Flask, request, render_template
import os
import logging
import redis
import socket
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.log_exporter import AzureEventHandler
from opencensus.ext.azure import metrics_exporter
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.stats import measure as measure_module
from opencensus.tags import tag_map as tag_map_module
from opencensus.trace import config_integration
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

# Initialize Flask application
app = Flask(__name__)

# Application Insights configuration
instru_key_insights = 'InstrumentationKey=f2faba01-466f-4aee-abe9-11257fc9ee58;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/;ApplicationId=4bd79552-f7ff-437b-b746-c5b78f04d32e'

# Set up logger for application insights
config_integration.trace_integrations(['logging'])
logger = logging.getLogger(__name__)
handler = AzureLogHandler(connection_string=instru_key_insights)
handler.setFormatter(logging.Formatter('%(traceId)s %(spanId)s %(message)s'))
logger.addHandler(handler)

logger.addHandler(AzureEventHandler(connection_string=instru_key_insights))
logger.setLevel(logging.INFO)

# Set up metrics exporter
exporter = metrics_exporter.new_metrics_exporter(
    enable_standard_metrics=True,
    connection_string=instru_key_insights
)
stats = stats_module.stats
view_manager = stats.view_manager
view_manager.register_exporter(exporter)

# Set up tracer for tracing
tracer = Tracer(
    exporter=AzureExporter(connection_string=instru_key_insights),
    sampler=ProbabilitySampler(1.0),
)

# Set up middleware for Flask application
middleware = FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string=instru_key_insights),
    sampler=ProbabilitySampler(rate=1.0)
)

# Load configuration from a config file or environment variables
app.config.from_pyfile('config_file.cfg')

# Get button values from environment variables or config
button1 = os.environ.get('VOTE1VALUE', app.config['VOTE1VALUE'])
button2 = os.environ.get('VOTE2VALUE', app.config['VOTE2VALUE'])
title = os.environ.get('TITLE', app.config['TITLE'])

# Redis Connection to a remote Redis server
REDIS = os.getenv('REDIS', 'localhost')  
REDIS_PWD = os.getenv('REDIS_PWD', '')  

# Redis Connection to another container
try:
    if "REDIS_PWD" in os.environ:
        r = redis.StrictRedis(host=REDIS,
                              port=6379,
                              password=REDIS_PWD)
    else:
        r = redis.Redis(REDIS)
    r.ping()  # Test the connection to Redis
except redis.ConnectionError:
    exit('Failed to connect to Redis, terminating.')

# Change title to hostname if configured to show host
if app.config.get('SHOWHOST') == "true":
    title = socket.gethostname()

# Initialize Redis counters for buttons
if not r.get(button1):
    r.set(button1, 0)
if not r.get(button2):
    r.set(button2, 0)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        # Get current vote values from Redis
        vote1 = r.get(button1).decode('utf-8')
        with tracer.span(name="Cats Vote") as span:
            logger.info("Tracing Cats Vote")
        
        vote2 = r.get(button2).decode('utf-8')
        with tracer.span(name="Dogs Vote") as span:
            logger.info("Tracing Dogs Vote")

        # Render the index page with vote values
        return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

    elif request.method == 'POST':
        if request.form['vote'] == 'reset':
            # Reset vote counts in Redis
            r.set(button1, 0)
            r.set(button2, 0)
            vote1 = r.get(button1).decode('utf-8')
            logger.info('Cats Vote Reset', extra={'custom_dimensions': {'Cats Vote': vote1}})

            vote2 = r.get(button2).decode('utf-8')
            logger.info('Dogs Vote Reset', extra={'custom_dimensions': {'Dogs Vote': vote2}})

            # Render the index page after resetting
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

        else:
            # Increment vote count in Redis
            vote = request.form['vote']
            r.incr(vote, 1)

            # Get current vote values after incrementing
            vote1 = r.get(button1).decode('utf-8')
            logger.info('Cats Vote', extra={'custom_dimensions': {'Cats Vote': vote1}})

            vote2 = r.get(button2).decode('utf-8')
            logger.info('Dogs Vote', extra={'custom_dimensions': {'Dogs Vote': vote2}})

            # Render the index page with updated vote values
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

if __name__ == "__main__":
    # Start the Flask application
    app.run(debug=True)  # Use debug=True for local development
    # app.run(host='0.0.0.0', threaded=True)  # Uncomment for deployment

