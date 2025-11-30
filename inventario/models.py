from django.conf import settings
from django.db import models


class Articulo(models.Model):
    """
    Representa un ítem de stock controlado por el sistema.
    """
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255)
    unidad_medida = models.CharField(max_length=20, default="unidad")  # ej: unidad, kg, caja
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ubicacion = models.CharField(max_length=100, blank=True)
    codigo_qr = models.CharField(
        max_length=100,
        unique=True,
        help_text="Valor que se codifica en el QR para identificar el artículo."
    )

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class MovimientoStock(models.Model):
    """
    Movimiento puntual de stock (ingreso, egreso o ajuste).
    """
    TIPO_INGRESO = "INGRESO"
    TIPO_EGRESO = "EGRESO"
    TIPO_AJUSTE = "AJUSTE"

    TIPO_CHOICES = [
        (TIPO_INGRESO, "Ingreso"),
        (TIPO_EGRESO, "Egreso"),
        (TIPO_AJUSTE, "Ajuste"),
    ]

    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="movimientos")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.TextField(blank=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_registrados"
    )

    class Meta:
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"{self.tipo} {self.cantidad} de {self.articulo.codigo} ({self.fecha_hora:%Y-%m-%d %H:%M})"


class Recepcion(models.Model):
    """
    Cabecera de una recepción controlada de mercadería.
    """
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_CONFIRMADA = "CONFIRMADA"

    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_CONFIRMADA, "Confirmada"),
    ]

    proveedor = models.CharField(max_length=255)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)
    numero_documento = models.CharField(max_length=50, blank=True)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recepciones_creadas"
    )

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Recepción #{self.id} - {self.proveedor} ({self.estado})"


class RecepcionItem(models.Model):
    """
    Ítems que componen una recepción (detalle).
    """
    recepcion = models.ForeignKey(Recepcion, on_delete=models.CASCADE, related_name="items")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="recepciones")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)

    # En la práctica el QR se escanea, pero lo dejamos explícito por si querés registrar el valor leído en cada ítem.
    valor_qr_leido = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.cantidad} x {self.articulo.codigo} en recepción #{self.recepcion_id}"
