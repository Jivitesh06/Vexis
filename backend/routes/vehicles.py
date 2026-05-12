"""
vehicles.py — Firestore-only vehicle management
No PostgreSQL dependency.
"""
from flask import Blueprint, request, jsonify
from utils.firebase_auth import firebase_required
from datetime import datetime

vehicles_bp = Blueprint('vehicles', __name__)


def _db():
    from firebase_admin import firestore
    return firestore.client()


# ── GET /api/vehicles ────────────────────────────────────────────────────
@vehicles_bp.route('/vehicles', methods=['GET'])
@firebase_required
def get_vehicles():
    try:
        uid  = request.user['uid']
        db   = _db()
        docs = db.collection('vehicles')\
                 .where('userId', '==', uid)\
                 .stream()

        vehicles = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            # Normalize timestamp to string
            if hasattr(d.get('createdAt'), 'isoformat'):
                d['created_at'] = d['createdAt'].isoformat()
            elif isinstance(d.get('createdAt'), str):
                d['created_at'] = d['createdAt']
            vehicles.append(d)

        # Sort vehicles in python (newest first)
        vehicles.sort(key=lambda x: x.get('created_at', '') or '', reverse=True)

        return jsonify({'vehicles': vehicles}), 200

    except Exception as e:
        print(f"[get_vehicles error] {e}")
        return jsonify({'vehicles': [], 'warning': str(e)}), 200


# ── POST /api/vehicles ───────────────────────────────────────────────────
@vehicles_bp.route('/vehicles', methods=['POST'])
@firebase_required
def add_vehicle():
    try:
        uid  = request.user['uid']
        data = request.get_json() or {}

        name          = (data.get('name') or '').strip()
        model         = (data.get('model') or '').strip()
        year          = data.get('year')
        vin           = (data.get('vin') or '').strip() or None
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
            return jsonify({'error': 'Owner number must be a number (e.g. 1, 2)'}), 400

        db  = _db()
        now = datetime.utcnow().isoformat()

        doc_ref = db.collection('vehicles').add({
            'userId':       uid,
            'name':         name,
            'model':        model,
            'year':         year,
            'vin':          vin,
            'plate_number': plate_number,
            'purchase_year':purchase_year,
            'owner_number': owner_number,
            'createdAt':    now,
        })

        vehicle_id = doc_ref[1].id
        vehicle = {
            'id':           vehicle_id,
            'userId':       uid,
            'name':         name,
            'model':        model,
            'year':         year,
            'vin':          vin,
            'plate_number': plate_number,
            'purchase_year':purchase_year,
            'owner_number': owner_number,
            'created_at':   now,
        }

        return jsonify({'message': 'Vehicle added successfully', 'vehicle': vehicle}), 201

    except Exception as e:
        print(f"[add_vehicle error] {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ── DELETE /api/vehicles/<id> ────────────────────────────────────────────
@vehicles_bp.route('/vehicles/<string:vehicle_id>', methods=['DELETE'])
@firebase_required
def delete_vehicle(vehicle_id):
    try:
        uid = request.user['uid']
        db  = _db()
        doc = db.collection('vehicles').document(vehicle_id).get()

        if not doc.exists:
            return jsonify({'error': 'Vehicle not found'}), 404

        if doc.to_dict().get('userId') != uid:
            return jsonify({'error': 'Not authorized'}), 403

        db.collection('vehicles').document(vehicle_id).delete()
        return jsonify({'message': 'Vehicle deleted'}), 200

    except Exception as e:
        print(f"[delete_vehicle error] {e}")
        return jsonify({'error': str(e)}), 500
