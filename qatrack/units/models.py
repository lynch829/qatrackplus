from django.conf import settings
from django.db import models
from django.utils.translation import ugettext as _

PHOTON = "photon"
ELECTRON = "electron"

#==========================================================================


class UnitType(models.Model):
    """Radiation Device Type

    Stores a device type for grouping individual :model:`unit`s together.
    For example, your Elekta Linacs might form one group, and your Tomo's
    another.

    TODO: improve model types
    """

    name = models.CharField(max_length=50, help_text=_("Name for this unit type"))
    vendor = models.CharField(max_length=50, help_text=_("e.g. Elekta"))
    model = models.CharField(max_length=50, help_text=_("Optional model name for this group"), null=True, blank=True)

    class Meta:
        unique_together = [("name", "model")]

    #---------------------------------------------------------------------------
    def __unicode__(self):
        """Display more descriptive name"""
        return "<UnitType(%s)>" % self.name

#============================================================================


class Modality(models.Model):
    """Treatment modalities

    defines available treatment modalities for a given :model:`unit1`

    """

    type_choices = ((PHOTON, "Photon"), (ELECTRON, "Electron"),)
    type = models.CharField(_("Treatement modality type"), choices=type_choices, max_length=20)
    energy = models.FloatField(help_text=_("Nominal energy (in MV for photons and MeV for electrons"))

    class Meta:
        verbose_name_plural = "Modalities"
        unique_together = [("type", "energy")]

    #---------------------------------------------------------------------------
    def __unicode__(self):
        if self.type == "photon":
            unit, particle = "MV", "Photon"
        else:
            unit, particle = "MeV", "Electron"
        return "<Modality(%.2f%s,%s)>" % (self.energy, unit, particle)

# class UnitManager(models.Manager):
    #---------------------------------------------------------------------------
#    def get_query_set(self):
#        return super(UnitManager,self).get_query_set().select_related("type")

#============================================================================


class Unit(models.Model):
    """Radiation devices

    Stores a single radiation device (e.g. Linac, Tomo unit, Cyberkinfe etc.)

    """

    number = models.PositiveIntegerField(null=False, unique=True, help_text=_("A unique number for this unit"))
    name = models.CharField(max_length=256, help_text=_("The display name for this unit"))
    serial_number = models.CharField(max_length=256, null=True, blank=True, help_text=_("Optional serial number"))
    location = models.CharField(max_length=256, null=True, blank=True, help_text=_("Optional location information"))
    install_date = models.DateField(null=True, blank=True, help_text=_("Optional install date"))

    type = models.ForeignKey(UnitType)

    modalities = models.ManyToManyField(Modality)
    # objects = UnitManager()

    class Meta:
        ordering = [settings.ORDER_UNITS_BY]

    #----------------------------------------------------------------------
    def __unicode__(self):
        return self.name
