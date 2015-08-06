import django.forms as forms
import django.db

from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import widgets, options
from django.shortcuts import render, HttpResponseRedirect
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.html import escape
from django.core.urlresolvers import reverse_lazy
from django.shortcuts import redirect

from admin_views.admin import AdminViews

import qatrack.qa.models as models


#============================================================================
class SaveUserMixin(object):
    """A Mixin to save creating user and modifiying user

    Set editable=False on the created_by and modified_by model you
    want to use this for.
    """

    #----------------------------------------------------------------------
    def save_model(self, request, obj, form, change):
        """set user and modified date time"""
        if not obj.pk:
            obj.created_by = request.user
            obj.created = timezone.now()
        obj.modified_by = request.user
        super(SaveUserMixin, self).save_model(request, obj, form, change)


#============================================================================
class BasicSaveUserAdmin(SaveUserMixin, admin.ModelAdmin):
    """manage reference values for tests"""


#============================================================================
class CategoryAdmin(admin.ModelAdmin):
    """QA categories admin"""
    prepopulated_fields = {'slug': ('name',)}


#============================================================================
class TestInfoForm(forms.ModelForm):

    reference_value = forms.FloatField(label=_("New reference value"), required=False,)
    reference_set_by = forms.CharField(label=_("Set by"), required=False)
    reference_set = forms.CharField(label=_("Date"), required=False)
    test_type = forms.CharField(required=False)

    class Meta:
        model = models.UnitTestInfo

    def __init__(self, *args, **kwargs):
        super(TestInfoForm, self).__init__(*args, **kwargs)
        readonly = ("test_type", "reference_set_by", "reference_set",)
        for f in readonly:
            self.fields[f].widget.attrs['readonly'] = "readonly"

        if self.instance:
            tt = self.instance.test.type
            i = [x[0] for x in models.TEST_TYPE_CHOICES].index(tt)
            self.fields["test_type"].initial = models.TEST_TYPE_CHOICES[i][1]

            if tt == models.BOOLEAN:
                self.fields["reference_value"].widget = forms.Select(choices=[("", "---"), (0, "No"), (1, "Yes")])
                self.fields["tolerance"].widget = forms.HiddenInput()

            elif tt == models.MULTIPLE_CHOICE or self.instance.test.is_string_type():
                self.fields["reference_value"].widget = forms.HiddenInput()
                self.fields['tolerance'].queryset = self.fields['tolerance'].queryset.filter(type=models.MULTIPLE_CHOICE)
            else:
                self.fields['tolerance'].queryset = self.fields['tolerance'].queryset.exclude(type=models.MULTIPLE_CHOICE)

            if tt != models.MULTIPLE_CHOICE and self.instance.reference:
                if tt == models.BOOLEAN:
                    val = int(self.instance.reference.value)
                else:
                    val = self.instance.reference.value
                self.initial["reference_value"] = val

            if self.instance.reference:
                r = self.instance.reference
                self.initial["reference_set_by"] = "%s" % (r.modified_by)
                self.initial["reference_set"] = "%s" % (r.modified)

    #----------------------------------------------------------------------
    def clean(self):
        """make sure valid numbers are entered for boolean data"""

        if (self.instance.test.type == models.MULTIPLE_CHOICE or self.instance.test.is_string_type()) and self.cleaned_data["tolerance"]:
            if self.cleaned_data["tolerance"].type != models.MULTIPLE_CHOICE:
                raise forms.ValidationError(_("You can't use a non-multiple choice tolerance with a multiple choice or string test"))
        else:
            if "reference_value" not in self.cleaned_data:
                return self.cleaned_data

            ref_value = self.cleaned_data["reference_value"]

            tol = self.cleaned_data["tolerance"]
            if tol is not None:
                if ref_value == 0 and tol.type == models.PERCENT:
                    raise forms.ValidationError(_("Percentage based tolerances can not be used with reference value of zero (0)"))

            if self.instance.test.type == models.BOOLEAN:
                if self.cleaned_data["tolerance"] is not None:
                    raise forms.ValidationError(_("Please leave tolerance field blank for boolean and multiple choice test types"))
        return self.cleaned_data


#----------------------------------------------------------------------
def test_type(obj):
    for tt, display in models.TEST_TYPE_CHOICES:
        if obj.test.type == tt:
            return display
test_type.admin_order_field = "test__type"


class SetMultipleReferencesAndTolerancesForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    contenttype = forms.CharField(widget=forms.HiddenInput, required=False)
    tolerance = forms.ModelChoiceField(queryset=models.Tolerance.objects.all())
    reference = forms.CharField(max_length=255)


class UnitTestInfoAdmin(AdminViews, admin.ModelAdmin):

    admin_views = (
        ('Copy References & Tolerances', 'redirect_to'),
    )

    def redirect_to(self, *args, **kwargs):
        return redirect(reverse_lazy("qa_copy_refs_and_tols"))

    actions = ['set_multiple_references_and_tolerances']
    form = TestInfoForm
    fields = (
        "unit", "test", "test_type",
        "reference", "reference_set_by", "reference_set", "tolerance",
        "reference_value",
    )
    list_display = ["test", test_type, "unit", "reference", "tolerance"]
    list_filter = ["unit", "test__category"]
    readonly_fields = ("reference", "test", "unit",)
    search_fields = ("test__name", "test__slug", "unit__name",)

    #----------------------------------------------------------------------
    def queryset(self, *args, **kwargs):
        """"""
        qs = super(UnitTestInfoAdmin, self).queryset(*args, **kwargs)
        return qs.select_related(
            "reference",
            "tolerance",
            "unit",
            "test",
        )

    #---------------------------------------------------------------------------
    def has_add_permission(self, request):
        """unittestinfo's are created automatically"""
        return False

    #---------------------------------------------------------------------------
    def form_valid(self, request, queryset, form):

        if form.is_valid():
            reference = form.cleaned_data['reference']
            tolerance = form.cleaned_data['tolerance']

            # Save the uti with the new references and tolerance
            # TODO: Combine with save method: save_model ?
            for uti in queryset:
                if uti.test.type != models.MULTIPLE_CHOICE:
                    if uti.test.type == models.BOOLEAN:
                        ref_type = models.BOOLEAN
                        if reference == 'True' or reference == 1:
                            reference = 1
                        else:
                            reference = 0
                    else:
                        ref_type = models.NUMERICAL
                    if reference not in ("", None):
                        if not(uti.reference and uti.reference.value == float(reference)):
                            try:
                                ref = models.Reference.objects.get(value=reference, type=ref_type)
                            except models.Reference.DoesNotExist:
                                ref = models.Reference(
                                    value=reference,
                                    type=ref_type,
                                    created_by=request.user,
                                    modified_by=request.user,
                                    name="%s %s" % (uti.unit.name, uti.test.name)[:255]
                                )
                                ref.save()
                            uti.reference = ref
                    else:
                        uti.reference = None
                uti.tolerance = tolerance
                uti.save()

            messages.success(request, "%s tolerances and references have been saved successfully." % queryset.count())
            return HttpResponseRedirect(request.get_full_path())

    #---------------------------------------------------------------------------
    def set_multiple_references_and_tolerances(self, request, queryset):

        testtypes = set(queryset.values_list('test__type', flat=True).distinct())

        # check if tests have the same type of tolerance, else return with error message
        if (len(testtypes) > 1 and 'multchoice' in testtypes or
                len(testtypes) > 1 and 'boolean' in testtypes):

            messages.error(request, "Multiple choice and/or boolean references and tolerances can't be set"
                                    " together with other test types")
            return HttpResponseRedirect(request.get_full_path())

        if 'apply' in request.POST:
            form = SetMultipleReferencesAndTolerancesForm(request.POST)
        else:
            form = SetMultipleReferencesAndTolerancesForm(initial={'contenttype': None})

        # if selected tests are NOT multiple choice or boolean, select all the tolerances which are NOT multiple choice or boolean
        if not 'boolean' in testtypes and not 'multchoice' in testtypes:
            tolerances = models.Tolerance.objects.exclude(type="multchoice").exclude(type="boolean")
            form.fields["tolerance"].queryset = tolerances

        # if selected tests are multiple choice select all the tolerances which are multiple choice
        elif 'multchoice' in testtypes:
            tolerances = models.Tolerance.objects.filter(type="multchoice")
            form.fields["contenttype"].initial = 'multchoice'
            form.fields["tolerance"].queryset = tolerances
            form.fields["reference"].required = False
            form.fields["reference"].widget = forms.HiddenInput()

        # if selected tests are boolean select all the tolerances which are boolean
        elif 'boolean' in testtypes:
            form.fields["contenttype"].initial = 'boolean'
            form.fields["reference"].widget = forms.NullBooleanSelect()
            form.fields["tolerance"].required = False
            form.fields["tolerance"].widget = forms.HiddenInput()

        if 'apply' in request.POST and form.is_valid():
            return self.form_valid(request, queryset, form)
        else:
            context = {
                'queryset': queryset,
                'form': form,
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
            }
            return render(request, 'admin/qa/unittestinfo/set_multiple_refs_and_tols.html', context)

    set_multiple_references_and_tolerances.short_description = "Set multiple references and tolerances"

    #--------------------------------------------------------len(testtypes)--------------
    def save_model(self, request, test_info, form, change):
        """create new reference when user updates value"""

        if form.instance.test.type != models.MULTIPLE_CHOICE:

            if form.instance.test.type == models.BOOLEAN:
                ref_type = models.BOOLEAN
            else:
                ref_type = models.NUMERICAL
            val = form["reference_value"].value()
            if val not in ("", None):
                if not(test_info.reference and test_info.reference.value == float(val)):
                    try:
                        ref = models.Reference.objects.filter(value=val, type=ref_type)[0]
                    except IndexError:
                        ref = models.Reference(
                            value=val,
                            type=ref_type,
                            created_by=request.user,
                            modified_by=request.user,
                            name="%s %s" % (test_info.unit.name, test_info.test.name)[:255]
                        )
                        ref.save()
                    test_info.reference = ref
            else:
                test_info.reference = None

        super(UnitTestInfoAdmin, self).save_model(request, test_info, form, change)


#============================================================================
class TestListAdminForm(forms.ModelForm):
    """Form for handling validation of TestList creation/editing"""

    #----------------------------------------------------------------------
    def clean_sublists(self):
        """Make sure a user doesn't try to add itself as sublist"""
        sublists = self.cleaned_data["sublists"]
        if self.instance in sublists:
            raise django.forms.ValidationError("You can't add a list to its own sublists")

        if self.instance.pk and self.instance.testlist_set.count() > 0 and len(sublists) > 0:
            msg = "Sublists can't be nested more than 1 level deep."
            msg += " This list is already a member of %s and therefore"
            msg += " can't have sublists of it's own."
            msg = msg % ", ".join([str(x) for x in self.instance.testlist_set.all()])
            raise django.forms.ValidationError(msg)

        return sublists


#============================================================================
class TestListMembershipInlineFormSet(forms.models.BaseInlineFormSet):

    #---------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        qs = kwargs["queryset"].filter(test_list=kwargs["instance"]).select_related("test")
        kwargs["queryset"] = qs
        super(TestListMembershipInlineFormSet, self).__init__(*args, **kwargs)

    #----------------------------------------------------------------------
    def clean(self):
        """Make sure there are no duplicated slugs in a TestList"""
        super(TestListMembershipInlineFormSet, self).clean()

        if not hasattr(self, "cleaned_data"):
            # something else went wrong already
            return {}

        slugs = [f.instance.test.slug for f in self.forms if (hasattr(f.instance, "test") and not f.cleaned_data["DELETE"])]
        slugs = [x for x in slugs if x]
        duplicates = list(set([sn for sn in slugs if slugs.count(sn) > 1]))
        if duplicates:
            raise forms.ValidationError(
                "The following macro names are duplicated :: " + ",".join(duplicates)
            )
        return self.cleaned_data


#----------------------------------------------------------------------
def test_name(obj):
    return obj.test.name


def macro_name(obj):
    return obj.test.slug


#============================================================================
class TestListMembershipForm(forms.ModelForm):

    model = models.TestListMembership

    #----------------------------------------------------------------------
    def validate_unique(self):
        """skip unique validation.

        The uniqueness of ('test_list','test',) is already independently checked
        by the formset (looks for duplicate macro names).

        By making validate_unique here a null function, we eliminate a DB call
        per test list membership when saving test lists in the admin.
        """


#============================================================================
class TestListMembershipInline(admin.TabularInline):

    model = models.TestListMembership
    formset = TestListMembershipInlineFormSet
    form = TestListMembershipForm
    extra = 5
    template = "admin/qa/testlistmembership/edit_inline/tabular.html"
    readonly_fields = (macro_name,)
    raw_id_fields = ("test",)

    #---------------------------------------------------------------------------
    def label_for_value(self, value):
        try:
            name = self.test_names[value]
            return '&nbsp;<strong>%s</strong>' % escape(Truncator(name).words(14, truncate='...'))
        except (ValueError, KeyError):
            return ''

    #---------------------------------------------------------------------------
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # copied from django.contrib.admin.wigets so we can override the label_for_value function
        # for the test raw id widget
        db = kwargs.get('using')
        if db_field.name == "test":
            widget = widgets.ForeignKeyRawIdWidget(db_field.rel,
                                                   self.admin_site, using=db)
            widget.label_for_value = self.label_for_value
            kwargs['widget'] = widget

        elif db_field.name in self.raw_id_fields:
            kwargs['widget'] = widgets.ForeignKeyRawIdWidget(db_field.rel,
                                                             self.admin_site, using=db)
        elif db_field.name in self.radio_fields:
            kwargs['widget'] = widgets.AdminRadioSelect(attrs={
                'class': options.get_ul_class(self.radio_fields[db_field.name]),
            })
            kwargs['empty_label'] = db_field.blank and _('None') or None
        return db_field.formfield(**kwargs)

    #---------------------------------------------------------------------------
    def get_formset(self, request, obj=None, **kwargs):
        # hacky method for getting test names so they don't need to be looked up again
        # in the label_for_value in contrib/admin/widgets.py
        if obj:
            self.test_names = dict(obj.tests.values_list("pk", "name"))
        else:
            self.test_names = {}
        return super(TestListMembershipInline, self).get_formset(request, obj, **kwargs)


#============================================================================
class TestListAdmin(SaveUserMixin, admin.ModelAdmin):

    prepopulated_fields = {'slug': ('name',)}
    list_display = ("name", "slug", "modified", "modified_by",)
    search_fields = ("name", "description", "slug",)
    filter_horizontal = ("tests", "sublists", )

    form = TestListAdminForm
    inlines = [TestListMembershipInline]
    save_as = True

    class Media:
        js = (
            settings.STATIC_URL + "js/jquery-1.7.1.min.js",
            settings.STATIC_URL + "js/jquery-ui.min.js",
            settings.STATIC_URL + "js/m2m_drag_admin.js",
            settings.STATIC_URL + "js/admin_description_editor.js",
            settings.STATIC_URL + "ace/ace.js",
        )

    #----------------------------------------------------------------------
    def queryset(self, *args, **kwargs):
        qs = super(TestListAdmin, self).queryset(*args, **kwargs)
        return qs.select_related("modified_by")


#============================================================================
class TestAdmin(SaveUserMixin, admin.ModelAdmin):
    list_display = ["name", "slug", "category", "type"]
    list_filter = ["category", "type"]
    search_fields = ["name", "slug", "category__name"]
    save_as = True

    #============================================================================
    class Media:
        js = (
            settings.STATIC_URL + "js/jquery-1.7.1.min.js",
            settings.STATIC_URL + "js/test_admin.js",
            settings.STATIC_URL + "js/admin_description_editor.js",
            settings.STATIC_URL + "ace/ace.js",
        )


#----------------------------------------------------------------------
def unit_name(obj):
    return obj.unit.name
unit_name.admin_order_field = "unit__name"
unit_name.short_description = "Unit"


def freq_name(obj):
    return obj.frequency.name
freq_name.admin_order_field = "frequency__name"
freq_name.short_description = "Frequency"


def assigned_to_name(obj):
    return obj.assigned_to.name
assigned_to_name.admin_order_field = "assigned_to__name"
assigned_to_name.short_description = "Assigned To"


#============================================================================
class UnitTestCollectionAdmin(admin.ModelAdmin):
    # readonly_fields = ("unit","frequency",)
    filter_horizontal = ("visible_to",)
    list_display = ["test_objects_name", unit_name, freq_name, assigned_to_name, "active"]
    list_filter = ["unit__name", "frequency__name", "assigned_to__name"]
    search_fields = ["unit__name", "frequency__name", "testlist__name", "testlistcycle__name"]
    change_form_template = "admin/treenav/menuitem/change_form.html"
    list_editable = ["active"]
    save_as = True

    #----------------------------------------------------------------------
    def queryset(self, *args, **kwargs):
        qs = super(UnitTestCollectionAdmin, self).queryset(*args, **kwargs)
        return qs.select_related(
            "unit__name",
            "frequency__name",
            "assigned_to__name"
        ).prefetch_related(
            "tests_object",
        )


#============================================================================
class TestListCycleMembershipInline(admin.TabularInline):

    model = models.TestListCycleMembership
    raw_id_fields = ("test_list",)


#============================================================================
class TestListCycleAdmin(SaveUserMixin, admin.ModelAdmin):
    """Admin for daily test list cycles"""
    inlines = [TestListCycleMembershipInline]
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ("name", "slug",)

    #============================================================================
    class Media:
        js = (
            settings.STATIC_URL + "js/jquery-1.7.1.min.js",
            settings.STATIC_URL + "js/jquery-ui.min.js",
            settings.STATIC_URL + "js/collapsed_stacked_inlines.js",
            settings.STATIC_URL + "js/m2m_drag_admin.js",
            settings.STATIC_URL + "js/admin_description_editor.js",
            settings.STATIC_URL + "ace/ace.js",
        )


#============================================================================
class FrequencyAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    model = models.Frequency


#============================================================================
class StatusAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    model = models.TestInstanceStatus


#----------------------------------------------------------------------
def utc_unit_name(obj):
    return obj.unit_test_collection.unit.name
utc_unit_name.admin_order_field = "unit_test_collection__unit__name"
utc_unit_name.short_description = "Unit"


#====================================================================================
class TestListInstanceAdmin(admin.ModelAdmin):
    list_display = ["__unicode__", utc_unit_name, "test_list", "work_completed", "created_by"]


#============================================================================
class ToleranceForm(forms.ModelForm):

    model = models.Tolerance

    #----------------------------------------------------------------------
    def validate_unique(self):
        super(ToleranceForm, self).validate_unique()
        if not self.instance.pk:
            params = forms.model_to_dict(self.instance)
            params.pop("id")
            if models.Tolerance.objects.filter(**params).count() > 0:
                self._update_errors({forms.models.NON_FIELD_ERRORS: ["Duplicate Tolerance. A Tolerance with these values already exists"]})


#====================================================================================
class ToleranceAdmin(BasicSaveUserAdmin):
    form = ToleranceForm


#====================================================================================
class AutoReviewAdmin(admin.ModelAdmin):
    list_display = (str, "pass_fail", "status")
    list_editable = ["pass_fail", "status"]


admin.site.register([models.Tolerance], ToleranceAdmin)
admin.site.register([models.AutoReviewRule], AutoReviewAdmin)
admin.site.register([models.Category], CategoryAdmin)
admin.site.register([models.TestList], TestListAdmin)
admin.site.register([models.Test], TestAdmin)
admin.site.register([models.UnitTestInfo], UnitTestInfoAdmin)
admin.site.register([models.UnitTestCollection], UnitTestCollectionAdmin)

admin.site.register([models.TestListCycle], TestListCycleAdmin)
admin.site.register([models.Frequency], FrequencyAdmin)
admin.site.register([models.TestInstanceStatus], StatusAdmin)
admin.site.register([models.TestListInstance], TestListInstanceAdmin)
