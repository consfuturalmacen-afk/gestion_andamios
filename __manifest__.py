{
    "name": "Gestión Andamios",
    "version": "19.0.1.0.0",
    "summary": "Control de inventario de piezas de andamios enviadas a obras",
    "description": """
Módulo para gestionar piezas de andamios, obras y movimientos de entrega/devolución.
""",
    "author": "Tu Empresa",
    "license": "LGPL-3",
    "category": "Inventory",
    "depends": ["base", "stock", "contacts", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "data/andamio_sequence.xml",
        "views/andamio_obra_views.xml",
        "views/andamio_pieza_views.xml",
        "views/andamio_movimiento_views.xml",
    ],
    "installable": True,
    "application": True,
}
