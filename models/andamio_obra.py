from collections import defaultdict

from odoo import fields, models


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
    # Campo legado para compatibilidad con datos previos y visualización en listas/kanban.
    ubicacion = fields.Char(
        string="Ubicación",
        related="ubicacion_id.complete_name",
        store=True,
        readonly=True,
    )
    cliente = fields.Char(string="Cliente")
    encargado_id = fields.Many2one("hr.employee", string="Encargado")
    movimiento_ids = fields.One2many("andamio.movimiento", "obra_id", string="Movimientos")
    piezas_en_obra = fields.Char(
        string="Piezas en Obra",
        compute="_compute_piezas_en_obra",
        help="Resumen de piezas actualmente en la obra (movimientos en estado En Obra).",
    )

    def _compute_piezas_en_obra(self):
        for obra in self:
            acumulado = defaultdict(float)
            movimientos_en_obra = obra.movimiento_ids.filtered(lambda mov: mov.estado == "en_obra")
            for movimiento in movimientos_en_obra:
                for linea in movimiento.lineas_ids:
                    if linea.pieza_id:
                        acumulado[linea.pieza_id.name] += linea.cantidad
            if acumulado:
                obra.piezas_en_obra = ", ".join(
                    f"{pieza}: {cantidad:g}" for pieza, cantidad in sorted(acumulado.items())
                )
            else:
                obra.piezas_en_obra = "Sin piezas en obra"
