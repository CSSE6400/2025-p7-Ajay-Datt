from flask import Blueprint, jsonify, request
from todo.models import db
from todo.models.todo import Todo
from datetime import datetime, timedelta
from celery.result import AsyncResult
from todo.tasks import ical  # Import the Celery task

api = Blueprint('api', __name__, url_prefix='/api/v1')


@api.route('/health')
def health():
    """Return a status of 'ok' if the server is running and listening to request"""
    return jsonify({"status": "ok"})


@api.route('/todos', methods=['GET'])
def get_todos():
    """Return the list of todo items"""
    completed = request.args.get('completed')
    window = request.args.get('window')

    todos = Todo.query.order_by(Todo.created_at.desc()).all()
    result = []
    for todo in todos:
        if completed is not None:
            if str(todo.completed).lower() != completed:
                continue
        if window is not None:
            date_limit = datetime.utcnow() + timedelta(days=int(window))
            if todo.deadline_at > date_limit:
                continue
        result.append(todo.to_dict())
    return jsonify(result)


@api.route('/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id):
    """Return the details of a todo item"""
    todo = Todo.query.get(todo_id)
    if todo is None:
        return jsonify({'error': 'Todo not found'}), 404
    return jsonify(todo.to_dict())


@api.route('/todos', methods=['POST'])
def create_todo():
    """Create a new todo item and return the created item"""
    if not set(request.json.keys()).issubset(set(('title', 'description', 'completed', 'deadline_at'))):
        return jsonify({'error': 'extra fields'}), 400

    if "title" not in request.json:
        return jsonify({'error': 'missing title'}), 400

    todo = Todo(
        title=request.json.get('title'),
        description=request.json.get('description'),
        completed=request.json.get('completed', False),
    )
    if 'deadline_at' in request.json:
        todo.deadline_at = datetime.fromisoformat(request.json.get('deadline_at'))

    db.session.add(todo)
    db.session.commit()
    return jsonify(todo.to_dict()), 201


@api.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """Update a todo item and return the updated item"""
    if not set(request.json.keys()).issubset(set(('title', 'description', 'completed', 'deadline_at'))):
        return jsonify({'error': 'extra fields'}), 400

    todo = Todo.query.get(todo_id)
    if todo is None:
        return jsonify({'error': 'Todo not found'}), 404

    todo.title = request.json.get('title', todo.title)
    todo.description = request.json.get('description', todo.description)
    todo.completed = request.json.get('completed', todo.completed)
    todo.deadline_at = request.json.get('deadline_at', todo.deadline_at)
    db.session.commit()

    return jsonify(todo.to_dict())


@api.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Delete a todo item and return the deleted item"""
    todo = Todo.query.get(todo_id)
    if todo is None:
        return jsonify({}), 200

    db.session.delete(todo)
    db.session.commit()
    return jsonify(todo.to_dict()), 200

@api.route('/test-celery', methods=['GET'])
def test_celery():
    """Trigger a simple test task"""
    task = ical.test_task.delay()
    return jsonify({
        'task_id': task.id,
        'task_status_url': f'{request.host_url}api/v1/todos/ical/{task.id}/status'
    }), 202

# ---------- CELERY ICAL TASK ENDPOINTS ----------

@api.route('/todos/ical', methods=['POST'])
def create_ical():
    """Trigger iCal generation as a background task"""
    todos = Todo.query.order_by(Todo.created_at.desc()).all()
    todo_input = [todo.to_dict() for todo in todos]
    task = ical.create_ical.delay(todo_input)
    return jsonify({
        'task_id': task.id,
        'task_url': f'{request.host_url}api/v1/todos/ical/{task.id}/status'
    }), 202


@api.route('/todos/ical/<task_id>/status', methods=['GET'])
def get_task(task_id):
    """Check the status of the iCal generation task"""
    task_result = AsyncResult(task_id)
    return jsonify({
        "task_id": task_id,
        "task_status": task_result.status,
        "result_url": f'{request.host_url}api/v1/todos/ical/{task_id}/result'
    }), 200


@api.route('/todos/ical/<task_id>/result', methods=['GET'])
def get_calendar(task_id):
    """Return the generated iCal file if ready"""
    task_result = AsyncResult(task_id)
    if task_result.status == 'SUCCESS':
        return task_result.result, 200, {'Content-Type': 'text/calendar'}
    else:
        return jsonify({'error': 'Task not finished'}), 404