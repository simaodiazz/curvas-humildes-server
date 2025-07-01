# Install the dependencies
pip install -r requirements.txt

# Run the application
# This configuration adapted to my processor (Intel Xeon E5 2695 v4 @ 2.40GHz @ 18 cores (36 threads))
gunicorn -w 5 -b 0.0.0.0:5002 'app:create_app(config_object_name="config")'
