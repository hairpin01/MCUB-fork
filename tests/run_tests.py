from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
import asyncio
import time

#!/usr/bin/env python3
"""
Test runner script for MCUB
"""
import sys
import subprocess
import argparse
from pathlib import Path

def run_tests(test_pattern=None, verbose=False, coverage=False):
    """Run pytest with appropriate configuration"""
    cmd = [sys.executable, '-m', 'pytest']
    
    # Add core directory to Python path
    core_path = str(Path(__file__).parent.parent / 'core')
    env = dict(os.environ)
    env['PYTHONPATH'] = f"{core_path}:{env.get('PYTHONPATH', '')}"
    
    if verbose:
        cmd.append('-v')
        
    if coverage:
        cmd.extend(['--cov=core', '--cov-report=term-missing'])
        
    if test_pattern:
        cmd.append(test_pattern)
    else:
        cmd.append('tests/')
        
    # Color output if supported
    cmd.append('--color=yes')
    
    print(f"Running tests with command: {' '.join(cmd)}")
    print(f"Python path: {env['PYTHONPATH']}")
    
    result = subprocess.run(cmd, env=env)
    return result.returncode

if __name__ == '__main__':
    import os
    
    parser = argparse.ArgumentParser(description='Run MCUB tests')
    parser.add_argument('pattern', nargs='?', help='Test pattern (e.g., test_kernel.py)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-c', '--coverage', action='store_true', help='Generate coverage report')
    
    args = parser.parse_args()
    
    sys.exit(run_tests(
        test_pattern=args.pattern,
        verbose=args.verbose,
        coverage=args.coverage
    ))
