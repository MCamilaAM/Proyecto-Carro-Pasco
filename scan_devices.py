import asyncio
import sys
from bleak import BleakScanner

# Ajustar codificación para la consola de Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

async def scan_ble():
    print("=== ESCANER DE DISPOSITIVOS BLUETOOTH (BLE) ===")
    print("Buscando dispositivos cercanos durante 6 segundos...\n")
    try:
        devices = await BleakScanner.discover(timeout=6.0)
        if not devices:
            print("[!] No se encontró ningún dispositivo Bluetooth activo.")
            return

        print(f"Se encontraron {len(devices)} dispositivos Bluetooth en el área:\n")
        pasco_found = False
        for d in devices:
            name = d.name or "Dispositivo Desconocido"
            address = d.address
            
            # Detectar si el dispositivo coincide con PASCO o con el ID 438
            if any(k in name.lower() for k in ["pasco", "control", "node", "438"]):
                pasco_found = True
                print(f"  ==> [¡ROBOT PASCO DETECTADO!] Nombre: '{name}' | MAC: {address}")
            else:
                print(f"  - Nombre: '{name}' | MAC: {address}")
        
        if not pasco_found:
            print("\n-------------------------------------------------------------")
            print("[!] ATENCION: El Bluetooth funciona, pero el robot '438-831' NO aparece.")
            print("-------------------------------------------------------------")
            print("Causas más comunes por las que el //control.Node no aparece en la lista:")
            print("1. EL ROBOT ESTÁ APAGADO O EN REPOSO:")
            print("   -> Mantén presionado el botón del //control.Node hasta que parpadee la luz.")
            print("2. EL ROBOT TIENE LA BATERÍA AGOTADA:")
            print("   -> Conéctalo por USB a cargar un momento y vuelve a encenderlo.")
            print("3. EL ROBOT YA ESTÁ CONECTADO A OTRO DISPOSITIVO/APP:")
            print("   -> Si abriste SPARKvue, PASCO Capstone o la app en un teléfono o tablet,")
            print("      ciérrala por completo. Los dispositivos PASCO se vuelven INVISIBLES")
            print("      mientras tengan una conexión Bluetooth activa.")
            print("4. DISPOSITIVO EMPAREJADO EN WINDOWS:")
            print("   -> Ve a 'Configuración de Windows -> Bluetooth' y si el 438-831 aparece")
            print("      como 'Emparejado/Guardado', presiona los 3 puntos y selecciona 'Quitar dispositivo'.")
            print("      (PASCO no requiere emparejamiento manual en Windows, conecta directo desde el script).")

    except Exception as e:
        print(f"Error al escanear Bluetooth: {e}")

if __name__ == "__main__":
    asyncio.run(scan_ble())
