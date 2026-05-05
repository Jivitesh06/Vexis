from flask import Blueprint, request, jsonify
from database import execute_query
from utils.firebase_auth import firebase_required, get_or_create_user

vehicles_bp = Blueprint('vehicles', __name__)


# ──────────────────────────────────────────────────────────────────
# GET /api/vehicles  — list all vehicles for current user
# ──────────────────────────────────────────────────────────────────
@vehicles_bp.route('/vehicles', methods=['GET'])
@firebase_required
def get_vehicles():
    try:
        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']
        vehicles = execute_query(
            """SELECT id, name, model, year, vin, plate_number, purchase_year, owner_number, TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at
               FROM vehicles
               WHERE user_id = %s
               ORDER BY created_at DESC""",
            (user_id,),
            fetchall=True
        )
        return jsonify({'vehicles': vehicles or []}), 200
    except Exception as e:
        print(f"[get_vehicles error] {e}")
        return jsonify({'error': 'Server error'}), 500


# ──────────────────────────────────────────────────────────────────
# POST /api/vehicles  — add a new vehicle
# ──────────────────────────────────────────────────────────────────
@vehicles_bp.route('/vehicles', methods=['POST'])
@firebase_required
def add_vehicle():
    try:
        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']
        data    = request.get_json() or {}

        name  = (data.get('name') or '').strip()
        model = (data.get('model') or '').strip()
        year  = data.get('year')
        vin   = (data.get('vin') or '').strip() or None
        plate_number  = (data.get('plate_number') or '').strip() or None
        purchase_year = (data.get('purchase_year') or '').strip() or None
        owner_number  = data.get('owner_number')

        if not name:
            return jsonify({'error': 'Vehicle nickname is required'}), 400
        if not model:
            return jsonify({'error': 'Car model is required'}), 400
        if not plate_number:
            return jsonify({'error': 'Plate number is required'}), 400
        if not purchase_year:
            return jsonify({'error': 'Purchase year is required'}), 400
        if not owner_number:
            return jsonify({'error': 'Owner number is required'}), 400

        if year:
            try:
                year = int(year)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid year'}), 400
                
        try:
            owner_number = int(owner_number)
        except (ValueError, TypeError):
            return jsonify({'error': 'Owner number must be a valid integer (e.g. 1, 2)'}), 400

        execute_query(
            """INSERT INTO vehicles (user_id, name, model, year, vin, plate_number, purchase_year, owner_number)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, name, model, year, vin, plate_number, purchase_year, owner_number),
            commit=True
        )

        vehicle = execute_query(
            """SELECT id, name, model, year, vin, plate_number, purchase_year, owner_number, TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at
               FROM vehicles
               WHERE user_id = %s
               ORDER BY created_at DESC LIMIT 1""",
            (user_id,),
            fetchone=True
        )

        return jsonify({'message': 'Vehicle added successfully', 'vehicle': vehicle}), 201

    except Exception as e:
        print(f"[add_vehicle error] {e}")
        return jsonify({'error': 'Server error'}), 500


# ──────────────────────────────────────────────────────────────────
# DELETE /api/vehicles/<id>  — delete a vehicle
# ──────────────────────────────────────────────────────────────────
@vehicles_bp.route('/vehicles/<int:vehicle_id>', methods=['DELETE'])
@firebase_required
def delete_vehicle(vehicle_id):
    try:
        # Get DB user_id
        db_user = get_or_create_user(request.user['uid'], request.user['email'])
        user_id = db_user['id']
        execute_query(
            "DELETE FROM vehicles WHERE id = %s AND user_id = %s",
            (vehicle_id, user_id),
            commit=True
        )
        return jsonify({'message': 'Vehicle deleted'}), 200
    except Exception as e:
        print(f"[delete_vehicle error] {e}")
        return jsonify({'error': 'Server error'}), 500
