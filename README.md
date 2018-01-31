# My Halite 2 Bot
This bot was created to play in a competition called Halite 2. My bot placed 51th overall and 1st out of the Australian Bots. Pretty happy with the result as I only found the competition with just over 1 week to go. Further details on the competition can be found here: https://halite.io 

## Pathfinding
The main issue I faced as with all Python Bots was timeouts. To solve this I used a vector approach with the following steps:
1. Navigate: Calculating the angle to set based on the distance and radius of the first planet to intersect the direct line to the target.
2. Resolve Collisions: This is made of 2 parts:
    1. Detect Collision: To detect the collision I ported the code that halite internally uses to detect collisions (collisionmap.py). This gives you the entity and time of the collision. To add to this I stepped through the remaining moves to determine the closest the 2 ships would possibly come in the turn if the collision did not occur.
    2. Avoid Collision: Once I new the closes part I drew a straight line between each entity and deflected them the minimum distance to avoid the collision. This was iterated over several times as with multiple ships each would have to move a little. There was also a multi-ship resolution and a random resolution that could be used in severe cases.

This resolved the time issues significantly and also stopped the ships from crashing in 99% of instances (I think there is still 1 or 2 bugs). The code for these features can be found in pathfinder.py and collisionmap.py

## Strategy
There are 5 major stages
1. Rush - I implemented rush to defend against rushes, not one of my favorate tactics though it worked well offensively as well.
2. Defend - For each enemy within 20 units of a planet I own assign the closest ship. 
3. Mine - Assign a ship to each unowned planet based on a simple algorithm
4. Attack - If the next best mine planet is owned by someone, assign ships to attack primaraly on the nearest ships.
5. Flee - If we are losing bad run away. I only implemented this with 2 hours to go in 30mins after I noticed people kept on beating me that were doing this. Got me from 100-50.

## Squadron
This was my first attempt at clumping together. It works and is what I use to keep close during rushes but I didn't get time to start using it during attack. larger groups seemed ineffective. Pathfinding kept the ships from crashing.

## Debug
The best thing I did was to pickle the MyBot object at the start of every turn so if I saw something I would type in the turn number and debug what happened.

## What I would have liked to do
1. Refactor the game_map data structures - I found myself iterating over things to find a single element. Swapping to using dictionaries would have significantly improve performance and made there use simpler.
1. Move defensive play - I tried retreating a little and it actually beat my bot I submitted but did poorly vs online as it was to passive. 
2. Implement a flocking algorithm
3. Improve my planet selection at the start
4. Machine Learning - I have some background in this but didn't really have the time


