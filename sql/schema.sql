-- schema.sql : normalized tables for the mess database (SQLite)

DROP TABLE IF EXISTS meals;
DROP TABLE IF EXISTS dishes;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS feedback;

CREATE TABLE dishes (
    dish_id      TEXT PRIMARY KEY,
    dish_name    TEXT NOT NULL UNIQUE,
    food_type    TEXT CHECK (food_type IN ('veg', 'egg', 'non-veg')),
    cost_per_kg  REAL NOT NULL            -- INR per kg of cooked food
);

CREATE TABLE calendar (
    date            TEXT PRIMARY KEY,     -- YYYY-MM-DD
    day_of_week     TEXT NOT NULL,
    academic_event  TEXT NOT NULL,        -- regular / exams / fest / long_weekend / diwali_break
    weather         TEXT NOT NULL         -- rain / clear
);

CREATE TABLE meals (
    date                 TEXT NOT NULL REFERENCES calendar(date),
    meal_type            TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner')),
    dish_id              TEXT NOT NULL REFERENCES dishes(dish_id),
    students_registered  INTEGER NOT NULL,
    headcount            INTEGER NOT NULL,
    food_prepared_kg     REAL NOT NULL,
    leftover_kg          REAL NOT NULL,   -- cooked but never served
    plate_waste_kg       REAL NOT NULL,   -- served but not eaten
    ran_out              INTEGER NOT NULL,-- 1 = food finished before students did
    plate_waste_imputed  INTEGER NOT NULL,
    PRIMARY KEY (date, meal_type)
);

CREATE TABLE feedback (
    feedback_id  INTEGER PRIMARY KEY,
    date         TEXT NOT NULL,
    meal_type    TEXT NOT NULL,
    rating       INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment_tag  TEXT
);
