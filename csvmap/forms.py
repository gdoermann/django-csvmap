from csvmap.mapping import decode_csv
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile,\
    InMemoryUploadedFile
from django.http import HttpResponse
from tempfile import TemporaryFile

class MapForm(forms.Form):
    encodings = {}
    MAP_NOT_FOUND = 'The file could not be imported. Please check that the file is in a valid format.'
    f = forms.FileField(label='Choose file')
    
    def __init__(self, maps, *args, **kwargs):
        """ The base form for mapping csv files
        @param maps: A list of MapOption objects to use for the import.
        """
        self.maps = maps
        super(MapForm, self).__init__(*args, **kwargs)
        self.decode()
    
    def decode(self):
        try:
            import chardet
        except:
            return
        
        files = self.files
        if files: 
            for key, f in files.items():
                f_data = f.readline()
                encoding = chardet.detect(f_data)['encoding']
                f.seek(0)
                self.encodings[key] = encoding
            
            # Actually decode files
            for key, encoding in self.encodings.items():
                if encoding.lower() not in ('utf-8', 'ascii'):
                    new_file = decode_csv(self.files[key], encoding)
                    f = self.files[key]
                    self.files[key].file = new_file
    
    _map = None
    def full_clean(self):
        super(MapForm, self).full_clean()
        if not self.is_bound or bool(self._errors):
            return # Already invalid
        
        # Valid if fields are valid AND the file uploaded matches a mapping protocol 
        for map in self.maps:
            if map.can_map(self.files['f']):
                self._map = map
                return
        # No map protocol could be used to import the data
        errors = self._errors.pop(forms.forms.NON_FIELD_ERRORS, self.error_class())
        errors.append(self.MAP_NOT_FOUND)
        self._errors[forms.forms.NON_FIELD_ERRORS] = errors
    
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