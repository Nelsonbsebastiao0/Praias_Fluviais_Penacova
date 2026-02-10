import sqlite3
from pathlib import Path
DB = Path(__file__).resolve().parents[1] / 'instance' / 'praias.db'
print('Usando DB:', DB)
if not DB.exists():
    print('Arquivo de banco não encontrado.')
    exit(1)
conn = sqlite3.connect(str(DB))
c = conn.cursor()
try:
    c.execute('SELECT id, name, email, role, password_hash, is_active FROM user')
    rows = c.fetchall()
    print('Usuarios encontrados:', len(rows))
    for r in rows:
        print({'id': r[0], 'name': r[1], 'email': r[2], 'role': r[3], 'has_password': bool(r[4]), 'is_active': bool(r[5])})
except Exception as e:
    print('Erro ao ler tabela user:', e)
finally:
    conn.close()
