import os
from flask import Flask
from routes.main_routes import register_routes


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get(
        "SECRET_KEY", "d383d8d81b3c431b8c792d669f9269d9587f19ee7fab0e072d22099621909c3a"
    )

    register_routes(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
