# Database Structure

This guide documents the column structure for each Google Sheet in the database.

## Rocket League Sheets
**Sheets**: `RL_Soccar`, `RL_Gridiron`, `RL_Hoops`, `RL_Dropshot`

### Columns (in order):
1. **Date** - Match date (text format, e.g. "2024-03-10")
2. **Match ID** - Sequential match number (integer)
3. **Blue_1** - Name of blue team player 1 (text or empty)
4. **Blue_2** - Name of blue team player 2 (text or empty)
5. **Blue_3** - Name of blue team player 3 (text or empty)
6. **Blue_4** - Name of blue team player 4 (text or empty)
7. **Goal_Blue** - Goals scored by blue team (integer)
8. **Goal_Orange** - Goals scored by orange team (integer)
9. **Orange_1** - Name of orange team player 1 (text or empty)
10. **Orange_2** - Name of orange team player 2 (text or empty)
11. **Orange_3** - Name of orange team player 3 (text or empty)
12. **Orange_4** - Name of orange team player 4 (text or empty)
13. **Overtime** - True/False if the match went to overtime (boolean)

---

## Mario Kart Sheet
**Sheet**: `MarioKart`

### Columns (in order):
1. **Date** - Race date (text format, e.g. "2024-03-10")
2. **Match ID** - Sequential race number (integer)
3. **1st** - Name of player who finished first (text or empty)
4. **2nd** - Name of player who finished second (text or empty)
5. **3rd** - Name of player who finished third (text or empty)
6. **4th** - Name of player who finished fourth (text or empty)
7. **5th** - Name of player who finished fifth (text or empty)
8. **6th** - Name of player who finished sixth (text or empty)
9. **7th** - Name of player who finished seventh (text or empty)
10. **8th** - Name of player who finished eighth (text or empty)

---

## FIFA Sheet
**Sheet**: `FIFA`

### Columns (in order):
1. **Date** - Match date (text format, e.g. "2024-03-10")
2. **Match ID** - Sequential match number (integer)
3. **Home Player** - Name of home player (text)
4. **Away Player** - Name of away player (text)
5. **Home Score** - Goals scored by home player in regular time (integer)
6. **Away Score** - Goals scored by away player in regular time (integer)
7. **Home Penalties Score** - Goals scored by home player in penalties (integer, 0 if no penalties)
8. **Away Penalties Score** - Goals scored by away player in penalties (integer, 0 if no penalties)
9. **Home Stars** - Star rating of home team (decimal 0.5-5.0)
10. **Away Stars** - Star rating of away team (decimal 0.5-5.0)

**FIFA Notes**:
- If the regular time score is different, the winner is determined by `Home Score` vs `Away Score`
- If the regular time score is tied:
  - If both penalty scores are 0, the match is a draw
  - If the penalty scores are different, the winner is determined by `Home Penalties Score` vs `Away Penalties Score`

---

## Players Sheet
**Sheet**: `Players`

### Columns:
1. **Color Code** - Hexadecimal color code (e.g. "FF5733")
2. **Rocket League** - Player name for Rocket League (text or empty)
3. **Mario Kart** - Player name for Mario Kart (text or empty)
4. **FIFA** - Player name for FIFA (text or empty)

Each row represents a color with associated player names for each game.
