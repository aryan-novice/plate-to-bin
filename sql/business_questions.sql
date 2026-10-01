-- business_questions.sql
-- Each block answers one question the mess committee actually asked.
-- Run them all with:  python src/run_sql.py

-- Q1. How big is the problem? Overall waste and what it cost.
SELECT
    COUNT(*)                                              AS meals_served,
    ROUND(SUM(m.food_prepared_kg) / 1000, 1)              AS food_cooked_tonnes,
    ROUND(SUM(m.leftover_kg + m.plate_waste_kg) / 1000, 1) AS food_wasted_tonnes,
    ROUND(100.0 * SUM(m.leftover_kg + m.plate_waste_kg)
          / SUM(m.food_prepared_kg), 1)                   AS waste_pct,
    ROUND(SUM((m.leftover_kg + m.plate_waste_kg) * d.cost_per_kg) / 100000, 1)
                                                          AS waste_cost_lakh_inr
FROM meals m
JOIN dishes d USING (dish_id);

-- Q2. Is it a cooking problem or an eating problem?
--     Leftover = cooked but never served (planning). Plate waste = served but not eaten (taste/portion).
SELECT
    meal_type,
    ROUND(SUM(leftover_kg))     AS leftover_kg,
    ROUND(SUM(plate_waste_kg))  AS plate_waste_kg,
    ROUND(100.0 * SUM(leftover_kg) / SUM(leftover_kg + plate_waste_kg), 1) AS leftover_share_pct
FROM meals
GROUP BY meal_type
ORDER BY CASE meal_type WHEN 'breakfast' THEN 1 WHEN 'lunch' THEN 2 ELSE 3 END;

-- Q3. Which day and meal wastes the most? (before the Feb-2026 pilot, to keep it fair)
SELECT
    c.day_of_week,
    ROUND(AVG(CASE WHEN m.meal_type = 'breakfast' THEN 100.0 * m.headcount / m.students_registered END), 1) AS bf_attendance_pct,
    ROUND(AVG(CASE WHEN m.meal_type = 'breakfast' THEN m.leftover_kg END), 1) AS bf_leftover_kg,
    ROUND(AVG(CASE WHEN m.meal_type = 'dinner'    THEN m.leftover_kg END), 1) AS dinner_leftover_kg
FROM meals m
JOIN calendar c USING (date)
WHERE m.date < '2026-02-01'
GROUP BY c.day_of_week
ORDER BY bf_leftover_kg DESC;

-- Q4. Which dishes do students leave on their plates? Ranked by plate-waste %.
WITH dish_stats AS (
    SELECT
        d.dish_name,
        COUNT(*) AS times_served,
        100.0 * SUM(m.plate_waste_kg) / SUM(m.food_prepared_kg - m.leftover_kg) AS plate_waste_pct,
        SUM(m.plate_waste_kg * d.cost_per_kg) AS plate_waste_cost
    FROM meals m
    JOIN dishes d USING (dish_id)
    GROUP BY d.dish_name
)
SELECT
    RANK() OVER (ORDER BY plate_waste_pct DESC) AS rnk,
    dish_name,
    times_served,
    ROUND(plate_waste_pct, 1)  AS plate_waste_pct,
    ROUND(plate_waste_cost)    AS plate_waste_cost_inr
FROM dish_stats
ORDER BY rnk
LIMIT 6;

-- Q5. The other side: which dishes run out before everyone has eaten?
SELECT
    d.dish_name,
    COUNT(*)                               AS times_served,
    SUM(m.ran_out)                         AS times_ran_out,
    ROUND(100.0 * SUM(m.ran_out) / COUNT(*), 1) AS ran_out_pct,
    ROUND(AVG(100.0 * m.headcount / m.students_registered), 1) AS avg_attendance_pct
FROM meals m
JOIN dishes d USING (dish_id)
WHERE m.meal_type <> 'breakfast'
GROUP BY d.dish_name
HAVING SUM(m.ran_out) > 0
ORDER BY ran_out_pct DESC
LIMIT 6;

-- Q6. How do campus events change demand? The kitchen only plans for Diwali.
SELECT
    c.academic_event,
    COUNT(DISTINCT m.date)                                    AS days,
    ROUND(AVG(100.0 * m.headcount / m.students_registered), 1) AS avg_attendance_pct,
    ROUND(100.0 * SUM(m.leftover_kg + m.plate_waste_kg) / SUM(m.food_prepared_kg), 1) AS waste_pct,
    SUM(m.ran_out)                                            AS meals_ran_out
FROM meals m
JOIN calendar c USING (date)
GROUP BY c.academic_event
ORDER BY waste_pct DESC;

-- Q7. Month-by-month waste cost, with change vs the previous month.
WITH monthly AS (
    SELECT
        substr(m.date, 1, 7) AS month,
        SUM((m.leftover_kg + m.plate_waste_kg) * d.cost_per_kg) AS waste_cost,
        COUNT(DISTINCT m.date) AS open_days
    FROM meals m
    JOIN dishes d USING (dish_id)
    GROUP BY month
)
SELECT
    month,
    open_days,
    ROUND(waste_cost / open_days) AS waste_cost_per_day_inr,
    ROUND(100.0 * (waste_cost / open_days)
          / LAG(waste_cost / open_days) OVER (ORDER BY month) - 100, 1) AS change_vs_prev_month_pct
FROM monthly
ORDER BY month;

-- Q8. Did the weekend-breakfast opt-in pilot (from 1 Feb 2026) work?
--     Difference-in-differences: weekend breakfasts (pilot) vs weekday breakfasts (no change).
--     Window: Nov 2025 - Mar 2026 so both periods include exams and holidays.
WITH b AS (
    SELECT
        CASE WHEN c.day_of_week IN ('Saturday', 'Sunday') THEN 'weekend (pilot)' ELSE 'weekday (control)' END AS grp,
        CASE WHEN m.date >= '2026-02-01' THEN 'after' ELSE 'before' END AS period,
        m.leftover_kg
    FROM meals m
    JOIN calendar c USING (date)
    WHERE m.meal_type = 'breakfast' AND m.date >= '2025-11-01'
)
SELECT
    grp,
    ROUND(AVG(CASE WHEN period = 'before' THEN leftover_kg END), 1) AS avg_leftover_before,
    ROUND(AVG(CASE WHEN period = 'after'  THEN leftover_kg END), 1) AS avg_leftover_after,
    ROUND(AVG(CASE WHEN period = 'after'  THEN leftover_kg END)
        - AVG(CASE WHEN period = 'before' THEN leftover_kg END), 1) AS change_kg
FROM b
GROUP BY grp;

-- Q9. Do low ratings predict plate waste? Average rating vs plate-waste % per dish.
WITH ratings AS (
    SELECT date, meal_type, AVG(rating) AS avg_rating, COUNT(*) AS n
    FROM feedback
    GROUP BY date, meal_type
)
SELECT
    d.dish_name,
    ROUND(SUM(r.avg_rating * r.n) / SUM(r.n), 2) AS avg_rating,
    ROUND(100.0 * SUM(m.plate_waste_kg) / SUM(m.food_prepared_kg - m.leftover_kg), 1) AS plate_waste_pct
FROM meals m
JOIN dishes d  USING (dish_id)
JOIN ratings r USING (date, meal_type)
GROUP BY d.dish_name
ORDER BY avg_rating;

-- Q10. Does rain keep students in the mess?
SELECT
    c.weather,
    m.meal_type,
    COUNT(*) AS meals,
    ROUND(AVG(100.0 * m.headcount / m.students_registered), 1) AS avg_attendance_pct,
    ROUND(100.0 * SUM(m.ran_out) / COUNT(*), 1) AS ran_out_pct
FROM meals m
JOIN calendar c USING (date)
WHERE c.academic_event = 'regular' AND m.meal_type <> 'breakfast'
GROUP BY c.weather, m.meal_type
ORDER BY m.meal_type, c.weather;
