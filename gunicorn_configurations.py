# http://docs.gunicorn.org/en/stable/settings.html
bind = '0.0.0.0:8000'

accesslog = '-'  # '-' makes gunicorn log to stdout
errorlog = '-'   # '-' makes gunicorn log to stderr
preload_app = True
timeout = 10
workers = 2
