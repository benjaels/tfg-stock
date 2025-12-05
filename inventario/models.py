from django.conf import settings
from django.db import models
from django.db.models import Max
from django.contrib.auth import get_user_model


class Categoria(models.Model):
    """
    Categorías para clasificar artículos.
    """
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    prefijo = models.CharField(max_length=10, blank=True, help_text="Prefijo para códigos de artículos (ej: CH-, P-, etc)")
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    """
    Datos de proveedor para órdenes y recepciones.
    """
    FORMA_CONTADO = "CONTADO"
    FORMA_CTA_CTE = "CTA_CTE"
    FORMA_CREDITO = "CREDITO"
    FORMA_PAGO_CHOICES = [
        (FORMA_CONTADO, "Contado efectivo"),
        (FORMA_CTA_CTE, "Cuenta corriente"),
        (FORMA_CREDITO, "Crédito"),
    ]

    razon_social = models.CharField(max_length=255)
    cuit = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default=FORMA_CONTADO)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["razon_social"]

    def __str__(self):
        return f"{self.razon_social} ({self.cuit})"


class UsuarioPerfil(models.Model):
    """
    Datos extra para usuarios internos.
    """
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name="perfil")
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"Perfil de {self.user.username}"


class Articulo(models.Model):
    """
    Representa un ítem de stock controlado por el sistema.
    """
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="articulos")
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
    Movimiento puntual de stock (ingreso, egreso, ajuste o eliminación).
    """
    TIPO_INGRESO = "INGRESO"
    TIPO_EGRESO = "EGRESO"
    TIPO_AJUSTE = "AJUSTE"
    TIPO_ELIMINACION = "ELIMINACION"

    TIPO_CHOICES = [
        (TIPO_INGRESO, "Ingreso"),
        (TIPO_EGRESO, "Egreso"),
        (TIPO_AJUSTE, "Ajuste"),
        (TIPO_ELIMINACION, "Eliminación"),
    ]

    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="movimientos")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
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


class OrdenCompra(models.Model):
    """
    Orden de compra para reponer artículos.
    """
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_RECIBIDA = "RECIBIDA"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente de recepción"),
        (ESTADO_RECIBIDA, "Recibida"),
    ]

    numero = models.PositiveIntegerField(unique=True, editable=False)
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordenes_compra",
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_recepcion = models.DateTimeField(null=True, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordenes_compra_creadas",
    )

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Orden de compra"
        verbose_name_plural = "Órdenes de compra"

    def save(self, *args, **kwargs):
        if not self.numero:
            ultimo = type(self).objects.aggregate(max_num=Max("numero")).get("max_num") or 0
            self.numero = ultimo + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"OC #{self.numero} - {self.proveedor}"


class OrdenCompraItem(models.Model):
    """
    Ítems solicitados en una orden de compra.
    """
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="items")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.articulo.codigo} en OC #{self.orden.numero}"
