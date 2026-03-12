"""
Test script to compare original RL engine vs pipeline architecture (v2).

This script runs both engines on the same dataset and compares outputs
to verify that the refactoring produces identical results.
"""
import json
from datetime import datetime


def compare_engines(sheet_name: str):
    """
    Compare original and v2 engines on the same sheet.
    
    Args:
        sheet_name: Name of the sheet to test
        
    Returns:
        dict with comparison results
    """
    print(f"\n{'='*70}")
    print(f"Testing sheet: {sheet_name}")
    print(f"{'='*70}\n")
    
    # Import engines
    from engine.engine_rl import get_RL_table as get_RL_table_v1
    from engine.engine_rl_v2 import get_RL_table as get_RL_table_v2
    
    # Run both engines
    print("Running original engine...")
    start = datetime.now()
    table_v1 = get_RL_table_v1(sheet_name)
    time_v1 = (datetime.now() - start).total_seconds()
    print(f"  ✓ Completed in {time_v1:.3f}s - {len(table_v1)} matches processed")
    
    print("\nRunning v2 pipeline engine...")
    start = datetime.now()
    table_v2 = get_RL_table_v2(sheet_name)
    time_v2 = (datetime.now() - start).total_seconds()
    print(f"  ✓ Completed in {time_v2:.3f}s - {len(table_v2)} matches processed")
    
    # Compare results
    print(f"\n{'-'*70}")
    print("Comparing outputs...")
    print(f"{'-'*70}\n")
    
    results = {
        'sheet_name': sheet_name,
        'num_matches': len(table_v1),
        'time_v1': time_v1,
        'time_v2': time_v2,
        'speedup': time_v1 / time_v2 if time_v2 > 0 else 0,
        'matches_identical': True,
        'differences': []
    }
    
    # Compare match by match
    if len(table_v1) != len(table_v2):
        print(f"❌ MISMATCH: Different number of matches!")
        print(f"   V1: {len(table_v1)} matches")
        print(f"   V2: {len(table_v2)} matches")
        results['matches_identical'] = False
        return results
    
    for i, (row_v1, row_v2) in enumerate(zip(table_v1, table_v2)):
        match_num = row_v1.get('Match', i+1)
        
        # Compare each field
        for key in row_v1.keys():
            val_v1 = row_v1[key]
            val_v2 = row_v2.get(key)
            
            if key in ['Total Delta', 'Total MMR', 'Uncertainty Factors']:
                # Compare dicts
                if not compare_dicts(val_v1, val_v2, tolerance=0.01):
                    results['matches_identical'] = False
                    results['differences'].append({
                        'match': match_num,
                        'field': key,
                        'v1': val_v1,
                        'v2': val_v2
                    })
            elif key in ['Blue Win Prob.', 'Orange Win Prob.', 'Inflation Factor']:
                # Compare floats with tolerance
                if abs(val_v1 - val_v2) > 0.01:
                    results['matches_identical'] = False
                    results['differences'].append({
                        'match': match_num,
                        'field': key,
                        'v1': val_v1,
                        'v2': val_v2
                    })
            else:
                # Compare exact
                if val_v1 != val_v2:
                    results['matches_identical'] = False
                    results['differences'].append({
                        'match': match_num,
                        'field': key,
                        'v1': val_v1,
                        'v2': val_v2
                    })
    
    # Print results
    if results['matches_identical']:
        print(f"✅ All {len(table_v1)} matches are IDENTICAL!")
    else:
        print(f"❌ Found {len(results['differences'])} differences:")
        for diff in results['differences'][:10]:  # Show first 10
            print(f"   Match {diff['match']}, field '{diff['field']}':")
            print(f"     V1: {diff['v1']}")
            print(f"     V2: {diff['v2']}")
        if len(results['differences']) > 10:
            print(f"   ... and {len(results['differences']) - 10} more")
    
    print(f"\n⚡ Performance: V2 is {results['speedup']:.2f}x {'faster' if results['speedup'] > 1 else 'slower'}")
    
    return results


def compare_dicts(dict1, dict2, tolerance=0.01):
    """Compare two dicts with numeric values, allowing tolerance."""
    if set(dict1.keys()) != set(dict2.keys()):
        return False
    
    for key in dict1:
        val1 = dict1[key]
        val2 = dict2[key]
        
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            if abs(val1 - val2) > tolerance:
                return False
        else:
            if val1 != val2:
                return False
    
    return True


def save_baseline(sheet_name: str, output_file: str = None):
    """Save baseline output from original engine for later comparison."""
    from engine.engine_rl import get_RL_table
    
    if output_file is None:
        output_file = f"baseline_{sheet_name}.json"
    
    print(f"Saving baseline for {sheet_name} to {output_file}...")
    table = get_RL_table(sheet_name)
    
    with open(output_file, 'w') as f:
        json.dump(table, f, indent=2, default=str)
    
    print(f"✓ Saved {len(table)} matches")
    return output_file


if __name__ == "__main__":
    import sys
    
    # Get sheet names from config
    from config import RL_GOAL_DIFFERENCE_FACTOR
    
    sheet_names = list(RL_GOAL_DIFFERENCE_FACTOR.keys())
    
    if len(sys.argv) > 1:
        # Test specific sheet
        sheet = sys.argv[1]
        if sheet in sheet_names:
            compare_engines(sheet)
        else:
            print(f"Unknown sheet: {sheet}")
            print(f"Available sheets: {sheet_names}")
    else:
        # Test all sheets
        print("\n" + "="*70)
        print("TESTING ALL RL SHEETS")
        print("="*70)
        
        all_results = []
        for sheet_name in sheet_names:
            try:
                result = compare_engines(sheet_name)
                all_results.append(result)
            except Exception as e:
                print(f"\n❌ ERROR testing {sheet_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        for result in all_results:
            status = "✅" if result['matches_identical'] else "❌"
            print(f"{status} {result['sheet_name']}: "
                  f"{result['num_matches']} matches, "
                  f"{result['speedup']:.2f}x speedup")
        
        total_identical = sum(1 for r in all_results if r['matches_identical'])
        print(f"\n{total_identical}/{len(all_results)} sheets passed")
