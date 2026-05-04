"""Tests for the TypeScript SDK CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from aksara import Model, fields
from aksara.api import ModelViewSet
from aksara.cli.main import cli


class Customer(Model):
    name = fields.String(max_length=100)

    class Meta:
        table_name = "customers"


class CustomerViewSet(ModelViewSet):
    model = Customer
    prefix = "/customers"


class TestSdkCli:
    """Tests for `aksara generate sdk`."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_generate_sdk_stdout(self):
        with patch("aksara.sdk.typescript.auto_discover_viewsets", return_value=[CustomerViewSet]):
            result = self.runner.invoke(cli, ["generate", "sdk", "--stdout"])

        assert result.exit_code == 0
        assert "export interface CustomerCreate" in result.output
        assert "async listCustomers" in result.output

    def test_generate_sdk_writes_file(self):
        with self.runner.isolated_filesystem():
            with patch("aksara.sdk.typescript.auto_discover_viewsets", return_value=[CustomerViewSet]):
                result = self.runner.invoke(cli, ["generate", "sdk", "--output", "frontend/api.ts"])

            assert result.exit_code == 0
            assert "Generated TypeScript SDK" in result.output
            with open("frontend/api.ts", "r", encoding="utf-8") as handle:
                content = handle.read()

        assert "export class AksaraClient" in content
        assert "async createCustomer" in content

    def test_generate_sdk_fails_without_viewsets(self):
        with patch("aksara.sdk.typescript.auto_discover_viewsets", return_value=[]):
            result = self.runner.invoke(cli, ["generate", "sdk", "--stdout"])

        assert result.exit_code != 0
        assert "No ViewSets discovered" in result.output