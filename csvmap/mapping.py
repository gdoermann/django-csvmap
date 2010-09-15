from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.forms.models import modelformset_factory
from django.utils.datastructures import SortedDict
import csv
import logging
import unicodedata
from django.utils.encoding import smart_unicode
from StringIO import StringIO
from vobject.base import ParseError

log = logging.getLogger('csvmap.mapping')

class ValueParser(object):
    def __init__(self, label, parser):
        """ parser must be callable """
        self.label = label
    
    def parse(self, value):
        return self.parser(value)
    
    def __str__(self):
        return self.label

class FileMapper(object):
    """ Create a form that maps the field label to the form """
    _map = SortedDict()
    
    def __init__(self, f, form, prefix = 'form', **kwargs):
        """ 
        @param f: The f file to map
        @param form: The form to use to map the file.  It looks maps the field labels to the f headers.
        args and kwargs are any f.DictReader args (which also include any f.reader args)
        encode and decode take encodings.codec encoders and decoders
        """
        self.f = f
        self.form = form
        self.prefix = prefix
        self._kwargs= kwargs
    
    _form = None
    def _get_form(self):
        return self._form
    def _set_form(self, form):
        """ You must give an initialized form so it can parse the form data, 
            or it must be able to initialize with no arguments"""
        if not isinstance(form, forms.Form):
            form = form()
        self._form = form
        # Parse the form information
        map = self._map = SortedDict()
        for name, field in form.fields.items():
            # This is the magic! It uses the field label and maps it to the field name
            # Field label can either be a ValueParser or a string
            map[name] = field.label
    form = property(_get_form, _set_form)
    
    _f = None
    def _get_f(self):
        return self._f
    def _set_f(self, f):
        self._f = f
        self.reader = None
        self._fieldnames = None
    f = property(_get_f, _set_f)
    
    _reader = None
    def _get_reader(self):
        if self._reader is None:
            if not self.f:
                raise ValueError('You must first set file to read.')
            self._reader = csv.DictReader(self.f, **self._kwargs)
        return self._reader
    def _set_reader(self, reader):
        self._reader = reader
    reader = property(_get_reader, _set_reader)
    
    _fieldnames = None
    def _get_fieldnames(self):
        if self._fieldnames is None:
            pos = self.f.tell()
            self.f.seek(0)
            reader = self.reader
            self._fieldnames = reader.fieldnames
            self.f.seek(pos)
        return self._fieldnames
    fieldnames = property(_get_fieldnames)
    
    _data = None
    n_forms = 0
    @property
    def data(self):
        """ Parse the formset data from the file """
        if not self._data:
            reader = self.reader
            data = {}
            form = self.form
            for d in reader:
                for name, header in self._map.items():
                    key = '%s-%i-%s' %(self.prefix, self.n_forms, name)
                    if d.has_key(str(header)):
                        parser = 'parse_%s' %(name)
                        if hasattr(form, parser):
                            m = getattr(form, parser)
                            data[key] = m(d)
                        else:
                            data[key] = d[header]
                    else:
                        data[key] = u''
                self.n_forms += 1
            data['%s-TOTAL_FORMS' %(self.prefix)] = self.n_forms
            data['%s-INITIAL_FORMS' %(self.prefix)] = 0
            data['%s-MAX_NUM_FORMS' %(self.prefix)] = None
            self._data = data
        return self._data
    
    def lines(self, formset):
        """ Dumps to a list of lines """
        lines = []
        lines.append([str(key) for key in self._map.values()])
        if isinstance(formset, list):
            forms = formset
        else:
            forms = formset.forms
        for form in forms:
            data = form.initial
            if form.is_bound and form.is_valid():
                data = form.cleaned_data
            line = []
            for name in self._map.keys():
                line.append(data[name])
            lines.append(line)
        return lines
    
    def dumps(self, formset):
        """ Takes a formset and converts it to a string """
        raw_lines = self.lines(formset)
        lines = [','.join(raw_lines)]
        return '\n'.join(lines)

class MapOption(object):
    """ 
    An option for the MapForm.  If the MapForm is given multiple options it will try all
    all the options in a row and the first one that can be used to parse the f will be used.
    It actually creates a formset of the given form, one form per f line, and checks to see
    if the forms are all valid.
    """
    CSV = 'f'
    XML = 'xml'
    
    def __init__(self, model, form, mapper = FileMapper, prefix = 'form', encoding = None, map_type=CSV):
        """ 
        @param model: The model that will be used in the formset
        @param form: The form to use in the formset
        @param mapper: This specifies how to map the f.  The default maps the form label to the f headers.
        """
        self.model, self.mapper_cls = model, mapper
        self.form = form
        self.prefix = prefix
        self.encoding = encoding
        self.map_type = map_type
    
    _required = None
    def _get_required(self):
        return self._required
    required = property(_get_required)
    
    def can_map(self, f):
        """
        @param f: The f file to check. 
        """
        # Get required fields
        required = self.Meta.required
        if required is None:
            required = []
            for field in self.form().fields.values():
                if field.required:
                    required.append(field.label)
        self._required = required
        if self.map_type == self.XML:
            return self._can_map_xml(f)
        else:
            return self._can_map(f)
    
    def _can_map_fields(self, fields):
        for field in self.required:
            if str(field) not in fields:
                return False
        return True
    
    def _can_map_xml(self, f):
        # check if you can reach all required fields
        raise NotImplementedError()
    
    def _can_map(self, f):
        """ Overridable check to see if you can map
        usually not required as you can change the mapper
        """
        
        # check headers against required fields
        pos = f.tell()
        f.seek(0)
        map = self.mapper(f)
        can_map = True
        try:
            fields = [str(field) for field in map.fieldnames]
            can_map = self._can_map_fields(fields)
        except (csv.Error, UnicodeError, ParseError):
            log.debug('File encoding does not match')
            can_map = False
        finally:
            f.seek(pos)
        return can_map
    
    def mapper(self, csv_file, **kwargs):
        """ 
        @rtype: FileMapper
        """
        return self.mapper_cls(csv_file, form = self.form, prefix = self.prefix, **kwargs)
    
    def formset_class(self, map):
        """ 
        Returns the formset class (just calls modelformset_factory)
        """
        return modelformset_factory(model = self.model, form = self.form,
            extra = map.n_forms, can_delete = True, can_order = True, max_num = map.n_forms)
    
    def formset(self, csv_file, **kwargs):
        """ 
        Returns the actual formset object which can be saved, altered, viewed, etc.
        """
        assert(self.can_map(csv_file))
        map = self.mapper(csv_file, **kwargs)
        cls = self.formset_class(map = map)
        return cls(map.data)
    
    class Meta:
        required = None
    
    def __str__(self):
        return "MapOption: %s" %self.form.__class__.__name__


def decode_csv(csv_file, encoding = 'utf-8'):
    """
    Provides an easy way to deal with encoding issues.  An example is Google Contacts
    f.  It exports as utf-16 which will throw errors when trying to parse using the 
    built-in f module in python 2.x.
    """
    if isinstance(csv_file, UploadedFile):
        csv_file = csv_file.file
    if encoding in ('ascii', 'utf-8'): # These don't need decoding
        return csv_file
    
    temp = StringIO()
    for line in csv_file:
        uline = smart_unicode(line, encoding = encoding, strings_only = True, errors = 'ignore')
        aline = unicodedata.normalize('NFKD', uline).encode('utf-8','ignore')
        aline.replace('\n', '').replace('\r', '') # This is a hack for utf-16 files
        temp.write(aline + '\n')
    temp.seek(0)
    return temp
