Sistema de alarma de sismos para raspberry PI


si no se tiene Python instalado en powershel o linux
pip install requests

debe ir a la carpeta raiz para ejecutar el script
para ejecutar el log python earthquakes.py


l log se guarda en el archivo system.log dentro de la carpeta data que está en el mismo directorio donde tienes el script earthquake.py.

Para verlo, puedes:

Abrir el archivo directamente con un editor de texto, por ejemplo:
        En Windows: abre data\system.log con el Bloc de notas o cualquier editor.
        En Linux/macOS: abre data/system.log con cualquier editor.

Ver el log en tiempo real desde la terminal o consola usando:
        En Linux/macOS:

        bash

         tail -f data/system.log

En Windows (PowerShell):

powershell

        Get-Content .\data\system.log -Wait

Esto te permitirá ver las entradas de log a medida que se generan.