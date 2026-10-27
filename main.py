import csv
import sys
import argparse

from algoritmos import cargar_mapa, dijkstra
from reparto import Paquete, Vehiculo, asignar_greedy, imprimir_plan, vol_paquete


def obtener_nodos(mapa):
    nodos = sorted([n for n in mapa.keys() if n != "Bodega - Centro"])
    return nodos


def main():
    ap = argparse.ArgumentParser(description="Reparto en Ibagué: greedy + Dijkstra + programación dinámica")
    ap.add_argument("--vehiculos", default="data/vehiculos.csv")
    ap.add_argument("--rutas", default="data/rutas.csv")
    ap.add_argument("--deposito", default="Bodega - Centro")
    ap.add_argument("--turbo", type=int, default=3)
    ap.add_argument("--van", type=int, default=8)
    ap.add_argument("--moto", type=int, default=4)
    args = ap.parse_args()

    # 1) Leer catálogo de vehículos
    catalogo = {}
    with open(args.vehiculos, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            catalogo[fila["tipo"].strip().lower()] = tuple(float(fila[c]) for c in ("peso_max_kg", "largo_m", "ancho_m", "alto_m"))

    # Crear unidades
    prefijos = {"turbo": "T", "van": "V", "moto": "M"}
    vehiculos = []
    for tipo, cantidad in [("turbo", args.turbo), ("van", args.van), ("moto", args.moto)]:
        if tipo not in catalogo:
            print(f"Error: tipo «{tipo}» no está en el catálogo", file=sys.stderr)
            return 1
        peso_max, largo, ancho, alto = catalogo[tipo]
        for n in range(1, cantidad + 1):
            vehiculos.append(Vehiculo(f"{prefijos[tipo]}-{n:02d}", tipo, peso_max, largo, ancho, alto))

    # 2) Cargar mapa base
    mapa_base = cargar_mapa(args.rutas)
    if args.deposito not in mapa_base:
        print(f"Error: depósito «{args.deposito}» no existe en el mapa", file=sys.stderr)
        return 1

    vecinos = {}
    with open(args.rutas, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            a, b, km = fila["origen"].strip(), fila["destino"].strip(), float(fila["distancia_km"])
            vecinos.setdefault(a, {})[b] = km
            vecinos.setdefault(b, {})[a] = km

    # 3) Ingreso
    print("=" * 70)
    print(" OPTIMIZADOR DE FLOTA Y RUTAS — Ibagué (Tolima)")
    print("=" * 70)
    print("\nIngrese los datos del paquete. Deje el ID vacío para terminar.\n")

    paquetes = []
    while True:
        pid = input("ID del paquete (ej. P001) o ENTER para finalizar: ").strip()
        if not pid:
            break
        try:
            peso = float(input("Peso (kg): ").strip().replace(",", "."))
            alto = float(input("Alto (m): ").strip().replace(",", "."))
            ancho = float(input("Ancho (m): ").strip().replace(",", "."))
            prof = float(input("Profundidad (m): ").strip().replace(",", "."))
        except ValueError:
            print("Valor numérico inválido. Intente nuevamente.\n")
            continue

        # Punto de llegada
        nodos_zona = obtener_nodos(mapa_base)
        print("\nSeleccione el PUNTO DE ENTREGA / ZONA a donde va el paquete (según rutas.csv):")
        for i, n in enumerate(nodos_zona, 1):
            print(f"  {i}) {n}")
        op_l = input("Opción: ").strip()
        try:
            punto_llegada = nodos_zona[int(op_l) - 1]
        except:
            print("Opción inválida.\n")
            continue
        print("\nIngrese la dirección MÁS DETALLADA del lugar de entrega:")
        print("(Calle, Carrera, Número, Manzana, Barrio, Sector, etc.)")
        dir_llegada = input("Dirección detallada: ").strip()
        if not dir_llegada:
            print("Debe ingresar una dirección detallada.\n")
            continue

        ubicacion_final = f"{dir_llegada} | {punto_llegada}"
        paquetes.append(Paquete(pid, peso, alto, ancho, prof, ubicacion_final))

        # Mostrar vehículo sugerido según tamaño/peso/medidas
        vol_p = alto * ancho * prof
        candidato = None
        for tipo in ["moto", "van", "turbo"]:
            pmax, l, a, al = catalogo[tipo]
            if peso <= pmax + 1e-9 and alto <= al + 1e-9 and ancho <= a + 1e-9 and prof <= l + 1e-9:
                candidato = tipo
                break
            if peso <= pmax + 1e-9 and vol_p <= l*a*al + 1e-12:
                if candidato is None:
                    candidato = tipo
        if candidato is None:
            print("\n[VEHÍCULO SUGERIDO según peso/medidas] Ningún vehículo del catálogo cabe por peso o medidas.")
        else:
            pmax, l, a, al = catalogo[candidato]
            print(f"\n[VEHÍCULO SUGERIDO según peso/medidas] {candidato.upper()} | carga máx {pmax} kg | bodega {l}x{a}x{al} m | vol. paquete {vol_p:.3f} m³")

        # Ruta desde bodega
        print("\n" + "-" * 70)
        print(f"Origen: {args.deposito} -> Destino: {punto_llegada}")
        print("-" * 70)
        dist_dij = dijkstra(vecinos, args.deposito)
        print(f"Distancia mínima desde {args.deposito} hasta {punto_llegada}: {dist_dij[punto_llegada]:.2f} km")
        print(f"Dirección detallada de entrega: {dir_llegada}")
        print("-" * 70 + "\n")
        print(f"Paquete {pid} registrado con éxito.\n")

    if not paquetes:
        print("No se ingresaron paquetes. Saliendo...", file=sys.stderr)
        return 1

    # Agregar zonas al mapa
    mapa = dict(mapa_base)
    for p in paquetes:
        try:
            zona = p.ubicacion.split("|")[-1].strip()
        except:
            zona = list(mapa_base.keys())[0] if mapa_base else args.deposito
        if zona not in mapa:
            mapa[zona] = dict(mapa_base[zona])
        if p.ubicacion not in mapa:
            distz = mapa[zona]
            nuevas = dict(distz)
            for k in nuevas:
                nuevas[k] = nuevas[k] + 0.1
            nuevas[p.ubicacion] = 0.0
            mapa[p.ubicacion] = nuevas
            for n in mapa:
                if n != p.ubicacion and p.ubicacion not in mapa[n]:
                    mapa[n][p.ubicacion] = nuevas[n] if n in nuevas else distz.get(n, 9999) + 0.1

    plan, sin_asignar = asignar_greedy(vehiculos, paquetes, mapa, args.deposito)

    print("=" * 70)
    print(" PLAN DE ENTREGA — Ibagué (Tolima)")
    print("=" * 70)
    print(f"Métodos: GREEDY (asignación) | DIJKSTRA (distancias mínimas) | PROG. DINÁMICA (Held-Karp, orden de ruta)")
    imprimir_plan(plan, sin_asignar, len(paquetes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
