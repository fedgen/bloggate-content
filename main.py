from routes import *
from flask_cors import CORS
app.register_blueprint(routes)

@app.route("/")
def hello():
    return "Hello World!"


if __name__ == '__main__':
    app.run()
