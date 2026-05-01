import json
import requests
import urllib3
import gzip
from flask import Flask, request, jsonify
from flask_cors import CORS
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import GuildTotalActivityPoints_pb2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

app.config['JSON_SORT_KEYS'] = False
if hasattr(app, 'json'):
    app.json.sort_keys = False

CORS(app)

AeSkEy = b'Yg&tc%DEuh6%Zc^8'
AeSiV = b'6oyZDr22E3ychjM%'

REGIONS = {
    "IND": {"name": "India", "server": "https://client.ind.freefiremobile.com/"},
    "ME": {"name": "Middle East", "server": "https://clientbp.ggpolarbear.com/"},
    "BD": {"name": "Bangladesh", "server": "https://clientbp.ggpolarbear.com/"},
    "PK": {"name": "Pakistan", "server": "https://clientbp.ggpolarbear.com/"},
    "BR": {"name": "Brazil", "server": "https://client.us.freefiremobile.com/"},
    "ID": {"name": "Indonesia", "server": "https://clientbp.ggpolarbear.com/"},
    "RU": {"name": "Russia", "server": "https://clientbp.ggpolarbear.com/"},
    "TH": {"name": "Thailand", "server": "https://clientbp.ggpolarbear.com/"},
    "TW": {"name": "Taiwan", "server": "https://clientbp.ggpolarbear.com/"}
}

CREDENTIALS = {
    "IND": {"uid": "4751039725", "password": "T10-DEV-44snbtsm"},
    "ME": {"uid": "4760349258", "password": "T10-DEV-W8SNLODZ"},
    "BD": {"uid": "4760410571", "password": "T10-DEV-OSS8ETWG"},
    "PK": {"uid": "4760419502", "password": "T10-DEV-0F4PD7AC"},
    "ID": {"uid": "4760424707", "password": "T10-DEV-QZZD6MEF"},
    "TH": {"uid": "4760428726", "password": "T10-DEV-PXWKV9MJ"},
    "BR": {"uid": "4761907118", "password": "8C75E0AEE7F6A0C1451C9B4FBC2825EAE46E1F9EEA30E88952629C0F6A579616"},
    "RU": {"uid": "4763771294", "password": "T10-DEV-ZTKXMWF1"},
    "TW": {"uid": "4763772215", "password": "T10-DEV-MILVLVNP"}
}

RANKS =[
    "Default", "Silver 1", "Silver 2", "Silver 3", "Gold 1",
    "Gold 2", "Gold 3", "Gold 4", "Platinum 1", "Platinum 2", "Platinum 3",
    "Platinum 4", "Platinum 5", "Diamond 1", "Diamond 2", "Diamond 3", "Diamond 4",
    "Diamond 5", "Heroic"
]

def get_rank_name(rank_value):
    if 1 <= rank_value <= len(RANKS):
        return RANKS[rank_value - 1]
    return str(rank_value)

def enc(d):
    return AES.new(AeSkEy, AES.MODE_CBC, AeSiV).encrypt(pad(d, 16))

def dec(d):
    try:
        return unpad(AES.new(AeSkEy, AES.MODE_CBC, AeSiV).decrypt(d), 16)
    except Exception:
        return d

def get_jwt_token(uid, password):
    url = f"https://spidey-jwt-gen.vercel.app/guest?uid={uid}&password={password}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json().get("token")
    except Exception:
        pass
    return None

@app.route('/regions', methods=['GET'])
def get_regions():
    region_list =[{"code": code, "name": data["name"]} for code, data in REGIONS.items()]
    return jsonify(region_list)

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    query = request.args.get('region', 'IND').strip().upper()
    target_region = "IND"

    for code, data in REGIONS.items():
        if query == code or query == data["name"].upper():
            target_region = code
            break
            
    r_data = REGIONS[target_region]
    creds = CREDENTIALS.get(target_region, {})

    if not creds.get("uid") or not creds.get("password"):
        return jsonify({"error": f"Credentials missing for region {target_region}"}), 400

    jwt_token = get_jwt_token(creds["uid"], creds["password"])
    if not jwt_token:
        return jsonify({"error": "Failed to get JWT token from external API"}), 401

    game_headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-S908E Build/TP1A.220624.014)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.11f1",
        "ReleaseVersion": "OB53",
        "Content-Type": "application/octet-stream",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        api_endpoint = f"{r_data['server'].rstrip('/')}/Leaderboard"
        
        prefix = bytes.fromhex("08ef073064")
        region_bytes = target_region.encode('utf-8')
        req_payload = prefix + bytes([0x42, len(region_bytes)]) + region_bytes
        
        encrypted_req = enc(req_payload)
        
        response = requests.post(api_endpoint, headers=game_headers, data=encrypted_req, timeout=15, verify=False)
        
        decrypted = dec(response.content)
        if decrypted.startswith(b'\x1f\x8b'):
            decrypted = gzip.decompress(decrypted)
            
        try:
            pb_data = GuildTotalActivityPoints_pb2.Leaderboard()
            pb_data.ParseFromString(decrypted)
        except Exception as parse_error:
            readable_text = "".join([chr(b) if 32 <= b <= 126 else "." for b in decrypted])
            return jsonify({
                "error": "The server rejected the request and returned an error instead of the leaderboard.",
                "protobuf_error": str(parse_error),
                "server_response_hex": decrypted.hex(),
                "server_response_text": readable_text
            }), 500
        
        results =[]
        for entry in pb_data.entries:
            details = entry.profile.details
            
            approval_data = {}
            if details.auto_approval == 1:
                approval_data["auto_approval"] = "off"
            elif details.auto_approval == 2:
                approval_data["auto_approval"] = "on"
            else:
                approval_data["auto_approval"] = details.auto_approval
            
            if details.minimum_level_required > 0:
                approval_data["minimum_level_required"] = details.minimum_level_required
            
            if details.minimum_br_rank_required > 0:
                approval_data["minimum_br_rank_required"] = get_rank_name(details.minimum_br_rank_required)
                
            if details.minimum_cs_rank_required > 0:
                approval_data["minimum_cs_rank_required"] = get_rank_name(details.minimum_cs_rank_required)
            
            guild_obj = {
                "rank": entry.rank,
                "guild_id": details.guild_id,
                "guild_name": details.guild_name,
                "leader_uid": details.leader_uid,
                "guild_level": details.guild_level,
                "maximum_members": details.maximum_members,
                "total_members": details.total_members,
                "slogan": details.slogan,
                "region": details.region,
                "total_activity_points": details.total_activity_points,
                "weekly_activity_points": details.weekly_activity_points,
                "approval": approval_data
            }
            
            results.append(guild_obj)
            
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)