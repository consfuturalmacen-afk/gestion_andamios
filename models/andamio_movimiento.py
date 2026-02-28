from odoo import fields, models


class AndamioMovimiento(models.Model):
    _name = "andamio.movimiento"
    _description = "Movimiento de Andamios"

    obra_id = fields.Many2one("andamio.obra", string="Obra", required=True)
    fecha_entrega = fields.Date(string="Fecha de Entrega", required=True)
    lineas_ids = fields.One2many(
        "andamio.movimiento.linea", "movimiento_id", string="Líneas"
    )
    estado = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("en_obra", "En Obra"),
            ("devuelto", "Devuelto"),
        ],
        string="Estado",
        default="borrador",
        required=True,
    )


class AndamioMovimientoLinea(models.Model):
    _name = "andamio.movimiento.linea"
    _description = "Línea de Movimiento de Andamios"

    movimiento_id = fields.Many2one(
        "andamio.movimiento", string="Movimiento", required=True, ondelete="cascade"
    )
    pieza_id = fields.Many2one("andamio.pieza", string="Pieza", required=True)
    cantidad = fields.Float(string="Cantidad", required=True, default=1.0)
