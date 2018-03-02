
# This file is part of Libreosteo.
#
# Libreosteo is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Libreosteo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Libreosteo.  If not, see <http://www.gnu.org/licenses/>.
from rest_framework import serializers, validators
from libreosteoweb.models import *
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from datetime import date
from .validators import UniqueTogetherIgnoreCaseValidator
from .filter import get_name_filters, get_firstname_filters
from django.core.exceptions import ObjectDoesNotExist
from .file_integrator import Extractor


class WithPkMixin(object):
    def get_pk_field(self, model_field):
        return self.get_field(model_field)

def check_birth_date(value):
    if value > date.today():
        raise serializers.ValidationError({
            'birth_date' :
                _('Birth date is invalid')
        })

class PatientSerializer (serializers.ModelSerializer):
    current_user_operation = None
    birth_date = serializers.DateField(label=_('Birth date'), validators=[check_birth_date] )

    def validate_family_name(self, value):
        return get_name_filters().filter(value)

    def validate_first_name(self, value):
        return get_firstname_filters().filter(value)

    def validate_original_name(self, value):
        return get_name_filters().filter(value)

    class Meta:
        model = Patient
        fields='__all__'
        validators = [
            UniqueTogetherIgnoreCaseValidator(
                queryset=Patient.objects.all(),
                fields=('family_name', 'first_name', 'birth_date'),
                message = _('This patient already exists'),
            )
        ]

class PatientExportSerializer (serializers.ModelSerializer):
    birth_date = serializers.DateField(label=_('Birth date'),)

    class Meta:
        model = Patient
        fields = ('family_name', 'first_name', 'original_name', 'birth_date')

class UserInfoSerializer(serializers.ModelSerializer):
    def validate_last_name(self, value):
        return get_name_filters().filter(value)

    def validate_first_name(self, value):
        return get_name_filters().filter(value)
    class Meta :
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

class RegularDoctorSerializer(serializers.ModelSerializer):
    def validate_family_name(self, value):
        return get_name_filters().filter(value)

    def validate_first_name(self, value):
        return get_name_filters().filter(value)
    class Meta:
        model = RegularDoctor

class ExaminationExtractSerializer(WithPkMixin, serializers.ModelSerializer):
    therapeut = UserInfoSerializer()
    comments = serializers.SerializerMethodField('get_nb_comments')
    class Meta:
        model = Examination
        fields = ('id', 'reason', 'date', 'status', 'therapeut', 'type', 'comments')
        depth = 1

    def get_nb_comments(self, obj):
        return ExaminationComment.objects.filter(examination__exact=obj.id).count()

class ExaminationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", required=False, allow_null=True, read_only=True)
    therapeut_detail = UserInfoSerializer(source="therapeut", required=False, allow_null=True, read_only=True)
    patient_detail = PatientExportSerializer(source="patient", required=False, allow_null=True, read_only=True)
    class Meta:
        model = Examination
        fields= '__all__'


class CheckSerializer(serializers.Serializer):
    bank = serializers.CharField(required=False, allow_null=True)
    payer = serializers.CharField(required=False, allow_null=True)
    number = serializers.CharField(required=False, allow_null=True)

class ExaminationInvoicingSerializer(serializers.Serializer):
    status = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_null=True)
    paiment_mode = serializers.CharField(required=False, allow_null=True)
    amount = serializers.FloatField(required=False, allow_null=True)
    check = CheckSerializer()

    def validate(self, attrs):
        """
        Check that the invoicing is consistent
        """
        if attrs['status'] == 'notinvoiced':
            if attrs['reason'] is None or len(attrs['reason'].strip()) == 0:
                raise serializers.ValidationError(_("Reason is mandatory when the examination is not invoiced"))
        if attrs['status'] == 'invoiced':
            if attrs['amount'] is None or attrs['amount'] <= 0:
                raise serializers.ValidationError(_("Amount is invalid"))
            if attrs['paiment_mode'] is None or len(attrs['paiment_mode'].strip()) == 0 or attrs['paiment_mode'] not in ['check', 'cash', 'notpaid']:
                raise serializers.ValidationError(_("Paiment mode is mandatory when the examination is invoiced"))
            if attrs['paiment_mode'] == 'check':
                if attrs['check'] is None :
                    raise serializers.ValidationError(_("Check information is missing"))
                #if attrs['check']['bank'] is None or len(attrs['check']['bank'].strip()) == 0:
                #    raise serializers.ValidationError(_("Bank information is missing about the check paiment"))
                #if attrs['check']['payer'] is None or len(attrs['check']['payer'].strip()) == 0:
                #    raise serializers.ValidationError(_("Payer information is missing about the check paiment"))
                #if attrs['check']['number'] is None or len(attrs['check']['number'].strip()) == 0:
                #    raise serializers.ValidationError(_("Number information is missing about the check paiment"))
        return attrs


class ExaminationCommentSerializer(WithPkMixin, serializers.ModelSerializer):
    user_info = UserInfoSerializer(source="user", required=False, read_only=True)
    class Meta:
        model = ExaminationComment
        fields = '__all__'

class OfficeEventSerializer(WithPkMixin, serializers.ModelSerializer):

    class Meta:
        model = OfficeEvent
        fields = '__all__'

    patient_name = serializers.SerializerMethodField()
    translated_comment = serializers.SerializerMethodField()
    therapeut_name = UserInfoSerializer(source = 'user')

    def get_patient_name(self, obj):
        if (obj.clazz == "Patient"):
            patient = Patient.objects.get(id = obj.reference)
            return "%s %s" % (patient.family_name, patient.first_name)
        if (obj.clazz == "Examination"):
            try :
                examination = Examination.objects.get(id=obj.reference)
                patient = examination.patient
                return "%s %s" % (patient.family_name, patient.first_name)
            except ObjectDoesNotExist:
                pass
        return ""

    def get_translated_comment(self, obj):
        return _(obj.comment)


class TherapeutSettingsSerializer(WithPkMixin, serializers.ModelSerializer):
    class Meta:
        model = TherapeutSettings
        fields = '__all__'

class OfficeSettingsSerializer(WithPkMixin, serializers.ModelSerializer):
    class Meta:
        model = OfficeSettings
        fields = '__all__'

class InvoiceSerializer(WithPkMixin, serializers.ModelSerializer):
    status = serializers.IntegerField(source='examination.status')

    class Meta:
        model = Invoice
        fields = '__all__'

class UserOfficeSerializer(WithPkMixin, serializers.ModelSerializer):
    def validate_family_name(self, value):
        return get_name_filters().filter(value)

    def validate_first_name(self, value):
        return get_name_filters().filter(value)
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'is_staff', 'is_active')

class PasswordSerializer(serializers.Serializer):
     password = serializers.CharField(
        required=False
     )

class FileImportSerializer(WithPkMixin, serializers.ModelSerializer):
    _status = None
    class Meta:
        model = FileImport
        fields = '__all__'
    analyze = serializers.SerializerMethodField()
    extract = serializers.SerializerMethodField()

    def get_analyze(self, obj):
        if obj.analyze is not None:
            return obj.analyze

    def get_extract(self, obj):
        return Extractor().extract(obj)

class DocumentSerializer(WithPkMixin, serializers.ModelSerializer):
    class Meta :
        model = Document
        fields = '__all__'

class DocumentUpdateSerializer(WithPkMixin, serializers.ModelSerializer):
    class Meta :
        fields = ['title','notes','document_date']
        model = Document

class PatientDocumentSerializer(WithPkMixin, serializers.ModelSerializer):
    document = DocumentSerializer()
    patient = serializers.PrimaryKeyRelatedField(many=False, queryset=Patient.objects.all())
    class Meta :
        model = PatientDocument
        fields = '__all__'
        depth=2
    def create(self, validated_data):
        document_data = validated_data.pop('document')
        document_data['user'] = validated_data.pop('user')
        patient = validated_data.pop("patient")
        document = Document.objects.create(internal_date=datetime.today(), **document_data)
        document.clean()
        document.save()
        patient_doc = PatientDocument.objects.create(patient=patient, document=document,**validated_data)
        return patient_doc
