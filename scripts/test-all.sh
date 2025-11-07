#!/bin/bash
# Run all tests (backend + frontend)
#
# Usage:
#   bash ~/portfolio-ai/scripts/test-all.sh
#   bash ~/portfolio-ai/scripts/test-all.sh --coverage  # With coverage reports

set -e  # Exit on first error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
BACKEND_DIR="$HOME/portfolio-ai/backend"
FRONTEND_DIR="$HOME/portfolio-ai/frontend"

# Parse arguments
COVERAGE=false
if [[ "$1" == "--coverage" ]]; then
    COVERAGE=true
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  Portfolio AI - Unified Test Runner${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
    echo ""
}

# Function to print success
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

#
# Backend Tests
#
print_header "Running Backend Tests"

cd "$BACKEND_DIR"

# Check if venv exists
if [ ! -d ".venv" ]; then
    print_error "Virtual environment not found at $BACKEND_DIR/.venv"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Run backend tests
if [ "$COVERAGE" = true ]; then
    echo "Running with coverage..."
    pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html
    BACKEND_EXIT=$?
    if [ $BACKEND_EXIT -eq 0 ]; then
        print_success "Backend coverage report generated at: $BACKEND_DIR/htmlcov/index.html"
    fi
else
    pytest tests/ -v
    BACKEND_EXIT=$?
fi

if [ $BACKEND_EXIT -eq 0 ]; then
    print_success "Backend tests passed"
else
    print_error "Backend tests failed (exit code: $BACKEND_EXIT)"
fi

#
# Frontend Tests
#
print_header "Running Frontend Tests"

cd "$FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_warning "node_modules not found, running npm install..."
    npm install
fi

# Run frontend tests
if [ "$COVERAGE" = true ]; then
    echo "Running with coverage..."
    npm run test:coverage -- --run
    FRONTEND_EXIT=$?
    if [ $FRONTEND_EXIT -eq 0 ]; then
        print_success "Frontend coverage report generated at: $FRONTEND_DIR/coverage/index.html"
    fi
else
    npm test -- --run
    FRONTEND_EXIT=$?
fi

if [ $FRONTEND_EXIT -eq 0 ]; then
    print_success "Frontend tests passed"
else
    print_error "Frontend tests failed (exit code: $FRONTEND_EXIT)"
fi

#
# Summary
#
print_header "Test Summary"

BACKEND_STATUS="PASSED"
FRONTEND_STATUS="PASSED"

if [ $BACKEND_EXIT -ne 0 ]; then
    BACKEND_STATUS="FAILED"
fi

if [ $FRONTEND_EXIT -ne 0 ]; then
    FRONTEND_STATUS="FAILED"
fi

echo "Backend:  $BACKEND_STATUS"
echo "Frontend: $FRONTEND_STATUS"
echo ""

if [ $BACKEND_EXIT -eq 0 ] && [ $FRONTEND_EXIT -eq 0 ]; then
    print_success "All tests passed! 🎉"
    if [ "$COVERAGE" = true ]; then
        echo ""
        echo "Coverage reports:"
        echo "  Backend:  $BACKEND_DIR/htmlcov/index.html"
        echo "  Frontend: $FRONTEND_DIR/coverage/index.html"
    fi
    exit 0
else
    print_error "Some tests failed"
    echo ""
    if [ $BACKEND_EXIT -ne 0 ]; then
        echo "  → Check backend tests: cd $BACKEND_DIR && pytest tests/ -v"
    fi
    if [ $FRONTEND_EXIT -ne 0 ]; then
        echo "  → Check frontend tests: cd $FRONTEND_DIR && npm test"
    fi
    exit 1
fi
