"""
Unit tests for Salesforce -> Snowflake/pandas type mapping.

No network, no credentials, no live Snowflake/Salesforce - pure function
tests against the mapping tables in lht.util.field_types.
"""
import pytest

from lht.exceptions import UnknownFieldTypeError
from lht.util import field_types


class TestSalesforceFieldType:
    """salesforce_field_type() maps a Salesforce describe() field dict to a
    Snowflake column type string."""

    def test_id_is_string_of_declared_length(self):
        assert field_types.salesforce_field_type({"type": "id", "length": 18}) == "string(18)"

    def test_boolean(self):
        assert field_types.salesforce_field_type({"type": "boolean"}) == "boolean"

    def test_string_is_not_length_bounded(self):
        # Regression guard: bounding string columns by Salesforce's declared
        # length used to make numeric-looking strings like "20" round-trip
        # through Snowflake as 20.0. See the comment in field_types.py.
        assert field_types.salesforce_field_type({"type": "string", "length": 255}) == "string"

    def test_textarea_is_unbounded_string(self):
        assert field_types.salesforce_field_type({"type": "textarea", "length": 32768}) == "string"

    def test_datetime(self):
        assert field_types.salesforce_field_type({"type": "datetime"}) == "timestamp_ntz"

    def test_date(self):
        assert field_types.salesforce_field_type({"type": "date"}) == "date"

    def test_currency(self):
        result = field_types.salesforce_field_type({"type": "currency", "precision": 18, "scale": 2})
        assert result == "number(18,2)"

    def test_double_uses_precision_and_scale(self):
        result = field_types.salesforce_field_type(
            {"type": "double", "precision": 18, "digits": 0, "scale": 2}
        )
        assert result == "NUMBER(18,2)"

    def test_int_uses_digits_when_precision_is_zero(self):
        result = field_types.salesforce_field_type(
            {"type": "int", "precision": 0, "digits": 8, "scale": 0}
        )
        assert result == "number(8,0)"

    def test_reference(self):
        assert field_types.salesforce_field_type({"type": "reference", "length": 18}) == "string(18)"

    def test_unknown_type_raises(self):
        with pytest.raises(UnknownFieldTypeError):
            field_types.salesforce_field_type({"type": "not_a_real_salesforce_type", "name": "Weird__c"})


class TestDfFieldType:
    """df_field_type() maps a Salesforce describe() field dict to the pandas
    dtype used before writing to Snowflake."""

    @pytest.mark.parametrize(
        "sf_type,expected_dtype",
        [
            ("id", "object"),
            ("boolean", "bool"),
            ("reference", "object"),
            ("string", "object"),
            ("double", "float64"),
            ("datetime", "datetime64"),
            ("date", "date"),
            ("currency", "float64"),
            ("percent", "float64"),
            ("int", "int64"),
        ],
    )
    def test_mapping(self, sf_type, expected_dtype):
        assert field_types.df_field_type({"type": sf_type}) == expected_dtype
