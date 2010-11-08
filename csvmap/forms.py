from django import forms
from django.http import HttpResponse
from django.conf import settings
from django.forms.util import ValidationError
from django.utils.translation import ugettext_lazy as _

class MapForm(forms.Form):
    default_error_messages = {
        'max_size': _(u"File too large for importing. Max size: %s KB" %(getattr(settings, 'MAX_IMPORT_SIZE', 100000)/1000)),
    }
    encodings = {}
    MAP_NOT_FOUND = 'The file could not be imported. Please check that the file is in a valid format.'
    f = forms.FileField(label='Choose file', help_text = "Max size: %s KB" %(getattr(settings, 'MAX_IMPORT_SIZE', 100000)/1000))
    
    def __init__(self, maps, *args, **kwargs):
        """ The base form for mapping csv files
        @param maps: A list of MapOption objects to use for the import.
        """
        self.maps = maps
        super(MapForm, self).__init__(*args, **kwargs)

    _map = None
    def full_clean(self):
        super(MapForm, self).full_clean()
        if not self.is_bound or bool(self._errors):
            return # Already invalid
        
        # Valid if fields are valid AND the file uploaded matches a mapping protocol 
        for map in self.maps:
            f = self.files['f']
            can_map = map.can_map(f)
            if can_map:
                self._map = map
                return
        # No map protocol could be used to import the data
        errors = self._errors.pop(forms.forms.NON_FIELD_ERRORS, self.error_class())
        errors.append(self.MAP_NOT_FOUND)
        self._errors[forms.forms.NON_FIELD_ERRORS] = errors
    
    def clean(self):
        f = self.files['f']
        if f.size > getattr(settings, 'MAX_IMPORT_SIZE', 100000): #100K is default
            raise ValidationError(self.default_error_messages['max_size'])
        return self.cleaned_data
    
    _formset = None
    @property
    def formset(self):
        if not self.is_valid():
            self._formset = None
            return None
        if self._formset is None:
            self._formset = self._map.formset(self.files['f'])
        return self._formset
    
    def save(self, *args, **kwargs):
        formset = self.formset
        if formset.is_valid() and not bool(args) and not bool(kwargs):
            return formset.save()
        
        saves = {}
        for form in formset.forms:
            if form.is_valid():
                saves[form] = form.save(*args, **kwargs)
        return saves
    
    @property
    def invalid_forms(self):
        if not self.formset:
            return None
        invalid_forms = []
        for form in self.formset.forms:
            if not form.is_valid():
                invalid_forms.append(form)
        return invalid_forms
    
    @property
    def invalid_csv(self):
        invalid_forms = self.invalid_forms
        if not bool(invalid_forms):
            return None
        return self._map.mapper(self.files['f']).dumps(invalid_forms)
    
    def invalid_csv_response(self, filename = 'invalid_rows'):
        """ Returns an HttpResponse of type csv """
        csv = self.invalid_csv
        response = HttpResponse(csv, mimetype = "text/csv")
        response['Content-Disposition'] = 'attachment; filename=%s.csv' %(filename)
        return response
