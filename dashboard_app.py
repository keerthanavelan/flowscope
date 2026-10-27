"""Local dashboard: python dashboard_app.py (http://127.0.0.1:5050)."""
import argparse
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType
from dashboard_data import execute, export_csv, FLOW_COUNTS, POLICY_LABELS
from experiments import experiment, experiment_csv


def create_app():
    app = Flask(__name__, template_folder='dashboard/templates', static_folder='dashboard/static')
    app.config['MAX_CONTENT_LENGTH'] = 16384

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/meta')
    def meta():
        return jsonify(policies=POLICY_LABELS, flow_counts=FLOW_COUNTS)

    @app.post('/api/run')
    def simulate():
        return jsonify(execute(request.get_json()))

    @app.post('/api/experiment')
    def simulate_experiment():
        return jsonify(experiment(request.get_json()))

    @app.post('/api/experiment/export/<kind>')
    def export_experiment(kind):
        if kind not in ('json', 'csv'):
            return jsonify(error='Unknown experiment export format.'), 404
        payload = experiment(request.get_json())
        response = jsonify(payload) if kind == 'json' else Response(experiment_csv(payload), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename="flowscope-experiment.{kind}"'
        return response

    @app.post('/api/export/<kind>')
    def export(kind):
        if kind not in ('json', 'metrics', 'polls'):
            return jsonify(error='Unknown export format.'), 404
        payload = execute(request.get_json())
        if kind == 'json':
            response = jsonify(payload)
        else:
            response = Response(export_csv(payload, kind), mimetype='text/csv')
        extension = 'json' if kind == 'json' else 'csv'
        response.headers['Content-Disposition'] = f'attachment; filename="sdn-{payload["run_id"]}-{kind}.{extension}"'
        return response

    @app.errorhandler(ValueError)
    @app.errorhandler(BadRequest)
    @app.errorhandler(UnsupportedMediaType)
    @app.errorhandler(RequestEntityTooLarge)
    def invalid(error):
        status = getattr(error, 'code', 400)
        return jsonify(error=str(error)), status

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5050)
    args = parser.parse_args()
    create_app().run(host='127.0.0.1', port=args.port, debug=False)
