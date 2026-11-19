"""
Arregla las rutas de MLflow despues de copiar o clonar el proyecto en otra computadora.

MLflow guarda en mlflow.db la ruta COMPLETA de la carpeta mlruns de la PC donde se corrio
el cuaderno (por ejemplo C:/Users/alexi/.../mlruns). En otra laptop esa ruta no existe y la
interfaz no encuentra las graficas ni los modelos. Este script cambia esa ruta vieja por la
ruta de la carpeta actual.

Uso (en la carpeta donde estan mlflow.db y mlruns, con la interfaz de MLflow apagada):
    python arreglar_rutas_mlflow.py

Se puede ejecutar las veces que haga falta (por ejemplo despues de cada git pull).
"""
import shutil
import sqlite3
from pathlib import Path

carpeta = Path.cwd()
db = carpeta / 'mlflow.db'
if not db.exists() or not (carpeta / 'mlruns').exists():
    raise SystemExit('Ejecuta este script en la carpeta donde estan mlflow.db y la carpeta mlruns.')

shutil.copy(db, carpeta / 'mlflow_backup.db')  # copia de seguridad antes de cambiar nada
con = sqlite3.connect(db)

# La ruta vieja de mlruns sale de la ubicacion de los experimentos: <ruta vieja>/mlruns/<id>
ubicaciones = [fila[0] for fila in con.execute('SELECT artifact_location FROM experiments') if fila[0]]
raices_viejas = set()
for ub in ubicaciones:
    normal = ub.replace('\\', '/').rstrip('/')
    raices_viejas.add(normal.rsplit('/', 1)[0])  # quita el /<id del experimento>

nueva_ruta = (carpeta / 'mlruns').resolve()

def formato_nuevo(vieja):
    # Mantiene el mismo estilo que usaba MLflow (file:///C:/... o ruta normal)
    return nueva_ruta.as_uri() if vieja.startswith('file:') else nueva_ruta.as_posix()

# Tablas y columnas de texto donde MLflow guarda rutas a los artifacts
tablas = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
cambios = 0
for vieja in raices_viejas:
    nueva = formato_nuevo(vieja)
    if vieja == nueva:
        continue
    variantes = {vieja, vieja.replace('/', '\\')}
    if vieja.startswith('file:///'):
        plano = vieja[len('file:///'):]
        variantes |= {plano, plano.replace('/', '\\')}
    for tabla in tablas:
        columnas = [c[1] for c in con.execute(f'PRAGMA table_info("{tabla}")')
                    if 'CHAR' in (c[2] or '').upper() or 'TEXT' in (c[2] or '').upper()]
        for col in columnas:
            for v in variantes:
                destino = nueva if v.startswith('file:') or v == vieja else (
                    nueva_ruta.as_posix() if '/' in v else str(nueva_ruta))
                cur = con.execute(f'UPDATE "{tabla}" SET "{col}" = REPLACE("{col}", ?, ?) '
                                  f'WHERE "{col}" LIKE ?', (v, destino, f'%{v}%'))
                cambios += cur.rowcount

if cambios == 0:
    print('Las rutas ya apuntan a esta carpeta. No hay nada que cambiar.')
else:
    con.commit()
    print(f'Listo: {cambios} rutas actualizadas.')
    print(f'Antes: {", ".join(sorted(raices_viejas))}')
    print(f'Ahora: {nueva_ruta}')
con.close()
