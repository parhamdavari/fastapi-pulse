#!/usr/bin/env bash
# FastAPI Pulse Test Suite Runner
#
# This script runs the complete test suite with coverage reporting.

set -e  # Exit on error

echo "FastAPI Pulse Test Suite"
echo "======================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    print_error "pytest is not installed"
    echo "Install with: pip install -e '.[test]'"
    exit 1
fi

# Run tests based on arguments
case "${1:-all}" in
    unit)
        print_status "Running unit tests..."
        pytest tests/unit/ -v -m unit
        ;;

    integration)
        print_status "Running integration tests..."
        pytest tests/integration/ -v -m integration
        ;;

    api)
        print_status "Running API tests..."
        pytest tests/api/ -v -m api
        ;;

    property)
        print_status "Running property-based tests..."
        pytest tests/property/ -v -m property
        ;;

    coverage)
        print_status "Running all tests with coverage..."
        pytest tests/ \
            --cov=fastapi_pulse \
            --cov-report=html \
            --cov-report=term-missing \
            --cov-fail-under=90

        print_status "Coverage report generated: htmlcov/index.html"
        ;;

    parallel)
        print_status "Running tests in parallel..."
        pytest tests/ -n auto -v
        ;;

    quick)
        print_status "Running quick test subset..."
        pytest tests/unit/ -v --tb=short
        ;;

    all)
        print_status "Running complete test suite..."
        pytest tests/ -v
        ;;

    ci)
        print_status "Running tests in CI mode..."
        pytest tests/ \
            --cov=fastapi_pulse \
            --cov-report=xml \
            --cov-report=term \
            --cov-fail-under=90 \
            --junit-xml=junit.xml \
            -v

        print_status "Coverage report: coverage.xml"
        print_status "JUnit report: junit.xml"
        ;;

    *)
        echo "Usage: $0 {unit|integration|api|property|coverage|parallel|quick|all|ci}"
        echo ""
        echo "Commands:"
        echo "  unit        - Run unit tests only"
        echo "  integration - Run integration tests only"
        echo "  api         - Run API endpoint tests only"
        echo "  property    - Run property-based tests only"
        echo "  coverage    - Run all tests with HTML coverage report"
        echo "  parallel    - Run tests in parallel with pytest-xdist"
        echo "  quick       - Run quick unit test subset"
        echo "  all         - Run all tests (default)"
        echo "  ci          - Run tests in CI mode with XML reports"
        exit 1
        ;;
esac

exit_code=$?

if [ $exit_code -eq 0 ]; then
    print_status "All tests passed! ✓"
else
    print_error "Some tests failed"
fi

exit $exit_code
