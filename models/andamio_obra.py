from collections import defaultdict

from odoo import api, fields, models


class AndamioObra(models.Model):
    _name = "andamio.obra"
    _description = "Obra"

    name = fields.Char(string="Nombre de la Obra", required=True)
    ubicacion_id = fields.Many2one(
        "stock.location",
        string="Ubicación Interna",
        domain=[("usage", "=", "internal")],
        required=True,
    )
    ubicacion = fields.Char(
        string="Ubicación",
        related="ubicacion_id.complete_name",
        store=True,
        readonly=True,
    )
    cliente = fields.Char(string="Cliente")
    encargado_id = fields.Many2one("hr.employee", string="Encargado")
    movimiento_ids = fields.One2many("andamio.movimiento", "obra_id", string="Movimientos")
    stock_move_ids = fields.Many2many(
        "stock.move",
        string="Movimientos de Stock",
        compute="_compute_stock_move_ids",
    )
    piezas_en_obra = fields.Char(string="Piezas en Obra", compute="_compute_resumen_obras")
    total_andamios_obra = fields.Float(string="Total Andamios en Obra", compute="_compute_resumen_obras")

    @api.depends("movimiento_ids.stock_move_ids", "ubicacion_id")
    def _compute_stock_move_ids(self):
        for obra in self:
            if not obra.ubicacion_id:
                obra.stock_move_ids = self.env["stock.move"]
                continue
            obra.stock_move_ids = self.env["stock.move"].search(
                [
                    ("state", "=", "done"),
                    "|",
                    ("location_id", "child_of", obra.ubicacion_id.id),
                    ("location_dest_id", "child_of", obra.ubicacion_id.id),
                ]
            )

    @api.depends(
        "movimiento_ids.estado",
        "movimiento_ids.tipo_movimiento",
        "movimiento_ids.lineas_ids.cantidad",
        "movimiento_ids.lineas_ids.pieza_id",
    )
    def _compute_resumen_obras(self):
        for obra in self:
            acumulado = defaultdict(float)
            for movimiento in obra.movimiento_ids.filtered(
                lambda m: m.estado in ("en_obra", "devuelto")
            ):
                signo = 1.0 if movimiento.tipo_movimiento == "salida" else -1.0
                for linea in movimiento.lineas_ids:
                    if linea.pieza_id:
                        acumulado[linea.pieza_id.name] += signo * linea.cantidad
            acumulado = {k: v for k, v in acumulado.items() if v > 0}
            obra.total_andamios_obra = sum(acumulado.values())
            obra.piezas_en_obra = (
                ", ".join(
                    f"{pieza}: {cantidad:g}" for pieza, cantidad in sorted(acumulado.items())
                )
                if acumulado
                else "Sin piezas en obra"
            )
