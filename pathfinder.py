import hlt
import logging
import math
from hlt.entity import Position, Entity
from collisionmap import process_events, CollisionMap, process_event_one_ship

# PLANET_NAVIGATION_FUDGE = 0.5   # Ship radius
PLANET_DOCK_DISTANCE = 2        # Radius are added
SHIP_AVOID_DISTANCE = 2         # Radius are added
VELOCITY_STEPS = 50


def make_angle_positive(angle):
    return (720 + angle) % 360


class Pathfinder:
    def __init__(self):
        self.turn = 0
        self.PLANET_NAVIGATION_FUDGE = 0.5      # This is dodgy
        pass

    def navigate(self, ship, target, game_map):
        self.PLANET_NAVIGATION_FUDGE = ship.radius

        closest_planet, distance = self.detect_first_planet_in_path(game_map, ship, target)
        distance_to_target = self.calculate_safe_distance_from_entity(ship, target)

        if distance_to_target < distance:
            if isinstance(target, hlt.entity.Ship):
                return self.navigate_to_ship(ship, target)
            elif closest_planet == target:
                return self.navigate_to_planet(ship, target)
            else:
                # We are navigating to a Position object
                return self.navigate_to_point(ship, target)
        else:
            ship.initial_target = target
            self.navigate_around_planet(ship, target, closest_planet, distance)
            #self.navigate(ship, self.navigate_around_planet(ship, target, closest_planet, distance), game_map)

    def detect_first_planet_in_path(self, game_map, ship, target):
        closest_distance = math.inf
        closest_planet = False
        for planet in game_map.all_planets():
            if (self.intersect_segment_circle(ship, target, planet, fudge=self.PLANET_NAVIGATION_FUDGE)) or (planet == target):
                distance = self.calculate_distance_between(ship, planet)
                if distance < closest_distance:
                    closest_planet = planet
                    closest_distance = distance

        return closest_planet, closest_distance

    def navigate_around_planet(self, ship, target, closest_planet, distance):
        angle_to_planet = make_angle_positive(self.calculate_angle_between(ship, closest_planet))
        angle_to_target = ship.calculate_angle_between(target)
        distance_to_target = self.calculate_safe_distance_from_entity(ship, target)
        speed = self.determine_speed(distance_to_target)

        if (closest_planet.radius + self.PLANET_NAVIGATION_FUDGE) > distance:
            optimal_distance = self.calculate_optimal_distance_from_planet(closest_planet.radius)
            angle_from_planet = make_angle_positive(math.degrees(math.atan(optimal_distance / hlt.constants.MAX_SPEED)))
        else:
            angle_from_planet = make_angle_positive(math.degrees(math.asin((closest_planet.radius + self.PLANET_NAVIGATION_FUDGE) / distance)))
            distance_to_perp_angle = math.cos(make_angle_positive(math.radians(angle_from_planet))) * distance

            if speed == hlt.constants.MAX_SPEED:
                # We don't really want the ship to stop closer that the optimal distance from the planet
                optimal_min_distance = distance_to_perp_angle - (hlt.constants.MAX_SPEED / 2)
                optimal_max_distance = distance_to_perp_angle + (hlt.constants.MAX_SPEED / 2)

                final_distance_from_perp_angle = distance_to_perp_angle - hlt.constants.MAX_SPEED

                if optimal_min_distance < final_distance_from_perp_angle and optimal_max_distance > final_distance_from_perp_angle:
                    # Adjust the angle to ensure the perfect distance
                    optimal_distance = self.calculate_optimal_distance_from_planet(closest_planet.radius)
                    angle_from_planet = make_angle_positive(math.degrees(math.atan(optimal_distance / hlt.constants.MAX_SPEED)) + angle_to_planet)

        if (angle_to_planet - 180) > angle_to_target:
            angle_to_target += 360
        if (angle_to_target - 180) > angle_to_planet:
            angle_to_planet += 360

        if angle_to_planet < angle_to_target:
            angle_to_point = angle_to_planet + angle_from_planet
        else:
            angle_to_point = angle_to_planet - angle_from_planet

        new_point = self.get_position_for_x_y_angle_magnitude(ship.x, ship.y, speed, make_angle_positive(angle_to_point))

        self.navigate_to_point(ship, new_point)
        #return self.get_position_for_x_y_angle_magnitude(ship.x, ship.y, speed, angle_to_point)

    def calculate_optimal_distance_from_planet(self, radius):
        return math.sqrt((radius + self.PLANET_NAVIGATION_FUDGE) ** 2 + (hlt.constants.MAX_SPEED/2) ** 2)

    def get_position_for_x_y_angle_magnitude(self, x, y, magnitude, angle):
        target_x = magnitude * math.cos(math.radians(angle)) + x
        target_y = magnitude * math.sin(math.radians(angle)) + y
        return hlt.entity.Position(target_x, target_y)

    def set_navigate(self, ship, target, distance_to_point):
        angle_to_point = ship.calculate_angle_between(target)
        speed = self.determine_speed(distance_to_point)

        ship.thrust(speed, angle_to_point, target)
        logging.info('Setting ship.id={} to thrust to attack'.format(ship.id))

    def determine_speed(self, distance_to_point):
        if distance_to_point < 0:
            return 0
        elif distance_to_point < hlt.constants.MAX_SPEED:
            return int(math.floor(distance_to_point + 0.01))     # 0.01 for float rounding
        else:
            return hlt.constants.MAX_SPEED

    def navigate_to_point(self, ship, point):
        return self.set_navigate(ship, point, self.calculate_safe_distance_from_point(ship, point))

    def navigate_to_ship(self, ship1, ship2):
        return self.set_navigate(ship1, ship2, self.calculate_safe_distance_from_ship(ship1, ship2))

    def navigate_to_planet(self, ship, planet):
        return self.set_navigate(ship, planet, self.calculate_safe_distance_from_planet(ship, planet))

    def calculate_safe_distance_from_entity(self, ship, entity):
        if isinstance(entity, hlt.entity.Ship):
            return self.calculate_safe_distance_from_ship(ship, entity)
        elif isinstance(entity, hlt.entity.Planet):
            return self.calculate_safe_distance_from_planet(ship, entity)
        else:
            return self.calculate_safe_distance_from_point(ship, entity)

    @staticmethod
    def calculate_safe_distance_from_point(ship, point):
        return ship.calculate_distance_between(point)

    @staticmethod
    def calculate_safe_distance_from_ship(ship1, ship2):
        return ship1.calculate_distance_between(ship2) -  (ship1.radius + ship2.radius + SHIP_AVOID_DISTANCE)

    @staticmethod
    def calculate_safe_distance_from_planet(ship, planet):
        return ship.calculate_distance_between(planet) - (ship.radius + planet.radius + PLANET_DOCK_DISTANCE)

    @staticmethod
    def calculate_distance_between(ship, target):
        """
        Calculates the distance between this object and the target.

        :param Entity target: The target to get distance to.
        :return: distance
        :rtype: float
        """
        return math.sqrt((target.x - ship.x) ** 2 + (target.y - ship.y) ** 2)

    @staticmethod
    def calculate_angle_between(ship, target):
        """
        Calculates the angle between this object and the target in degrees.

        :param Entity target: The target to get the angle between.
        :return: Angle between entities in degrees
        :rtype: float
        """
        return math.degrees(math.atan2(target.y - ship.y, target.x - ship.x)) % 360

    @staticmethod
    def intersect_segment_circle(start, end, circle, *, fudge=0.5):
        """
        Test whether a line segment and circle intersect.

        :param Entity start: The start of the line segment. (Needs x, y attributes)
        :param Entity end: The end of the line segment. (Needs x, y attributes)
        :param Entity circle: The circle to test against. (Needs x, y, r attributes)
        :param float fudge: A fudge factor; additional distance to leave between the segment and circle. (Probably set this to the ship radius, 0.5.)
        :return: True if intersects, False otherwise
        :rtype: bool
        """
        # Derived with SymPy
        # Parameterize the segment as start + t * (end - start),
        # and substitute into the equation of a circle
        # Solve for t
        dx = end.x - start.x
        dy = end.y - start.y

        a = dx ** 2 + dy ** 2
        b = -2 * (start.x ** 2 - start.x * end.x - start.x * circle.x + end.x * circle.x +
                  start.y ** 2 - start.y * end.y - start.y * circle.y + end.y * circle.y)
        c = (start.x - circle.x) ** 2 + (start.y - circle.y) ** 2

        if a == 0.0:
            # Start and end are the same point
            return start.calculate_distance_between(circle) <= circle.radius + fudge

        # Time along segment when closest to the circle (vertex of the quadratic)
        t = min(-b / (2 * a), 1.0)
        if t < 0:
            return False

        closest_x = start.x + dx * t
        closest_y = start.y + dy * t
        closest_distance = Position(closest_x, closest_y).calculate_distance_between(circle)

        return closest_distance <= circle.radius + fudge


    ### Start Collision Avoidance ###
    def resolve_collisions(self, game_map):
        MAX_COLLISION_LOOPS=20
        self.turn += 1
        collision_map = CollisionMap(game_map)

        logging.info(collision_map)

        self.previous_collisions = {}

        for i in range(MAX_COLLISION_LOOPS):
            logging.info('Collision Resolution loop {}'.format(i))
            events = process_events(game_map, collision_map)
            unique_collisions = self.remove_event_duplicates(events)

            # This will be the last loop
            if i > MAX_COLLISION_LOOPS - 5:
                for collision in unique_collisions:
                    self.check_for_collision_map_errors(collision, collision_map, game_map)

                    collision_2 = [collision[0], collision[2], collision[1], collision[3]]
                    self.check_for_collision_map_errors(collision_2, collision_map, game_map)
                    return

            if len(unique_collisions) == 0:
                logging.info('No collisions')
                break

            for collision in unique_collisions:
                # self.rotate_ship(collision, collision_map, game_map)
                ship = game_map.get_player(collision[1][0]).get_ship(collision[1][1])

                if collision[2][0] is None:
                    entity = game_map.get_planet(collision[2][1])
                else:
                    entity = game_map.get_player(collision[2][0]).get_ship(collision[2][1])

                try:
                    self.determine_collision_avoidance(ship, entity, collision, collision_map, game_map)
                except:
                    # There are some rare errors that I need to find....
                    logging.info('An unknown error occured')
                    ship.thrust(0, 0, hlt.entity.Position(ship.x, ship.y))

                if isinstance(ship, hlt.entity.Ship) and ship.magnitude > 0:
                    if ship.id in self.previous_collisions:
                        self.previous_collisions[ship.id].append([ship, entity, collision])
                    else:
                        self.previous_collisions[ship.id] = [[ship, entity, collision]]
                if isinstance(entity, hlt.entity.Ship) and entity.magnitude > 0:
                    if entity.id in self.previous_collisions:
                        self.previous_collisions[entity.id].append([entity, ship, collision])
                    else:
                        self.previous_collisions[entity.id] = [[entity, ship, collision]]

    def determine_collision_avoidance(self, ship, entity, collision, collision_map, game_map):
        if isinstance(ship, hlt.entity.Ship):
            if ship.id in self.previous_collisions:
                if len(self.previous_collisions[ship.id]) > 1:
                    for previous_collision in self.previous_collisions[ship.id]:
                        if previous_collision[1].id == entity.id:
                            return self.resolve_multi_target_collision(ship, entity, collision, collision_map, game_map)

        if isinstance(entity, hlt.entity.Ship):
            if entity.id in self.previous_collisions:
                if len(self.previous_collisions[entity.id]) > 1:
                    for previous_collision in self.previous_collisions[entity.id]:
                        if previous_collision[1].id == ship.id:
                            return self.resolve_multi_target_collision(entity, ship, collision, collision_map, game_map, swapped=True)

        return self.avoid_collision(ship, entity, collision)

    def avoid_collision(self, ship, entity, collision):
        logging.info('Avoid Collision')
        logging.info(ship)
        logging.info(entity)
        logging.info(collision)

        # We want to modifiy how much the ship moves based on
        #   If the ship is close to the target, deviate less
        #   If the ship is going slow, deviate less (will not move if speed is 0)
        if ship.distance_to_target == 0 and entity.distance_to_target == 0:
            # They both reached their targets
            init_ship_modifier = (ship.magnitude / hlt.constants.MAX_SPEED)
            init_entity_modifier = (entity.magnitude / hlt.constants.MAX_SPEED)
        else:
            init_ship_modifier = (ship.magnitude / hlt.constants.MAX_SPEED) * \
                            (ship.distance_to_target / (ship.distance_to_target + entity.distance_to_target))

            init_entity_modifier = (entity.magnitude / hlt.constants.MAX_SPEED) * \
                              (entity.distance_to_target / (entity.distance_to_target + ship.distance_to_target))

        if init_ship_modifier == 0 and init_entity_modifier == 0:
            return    # They are already colliding...

        ship_modifier = init_ship_modifier / (init_ship_modifier + init_entity_modifier)
        entity_modifier = init_entity_modifier / (init_ship_modifier + init_entity_modifier)

        logging.info('ship_modifer: {}   entity_modifer: {}'.format(ship_modifier, entity_modifier))

        if ship.magnitude == 0 and entity.magnitude == 0:
            raise(Exception('Both ships are not moving...'))

        # Note: By always taking the shortest path to something the rotation + distance modifier
        # should (almost) always keep the ship in range of the target

        # TODO: Check if the ships paths cross (below only works for co-liniar

        # Find where the collision first happened
        t = collision[3]
        ship_position = Position(ship.x + ship.vel_x * t, ship.y + ship.vel_y * t)
        entity_position = Position(entity.x + entity.vel_x * t, entity.y + entity.vel_y * t)

        logging.info('collision happened at ship_position: {}   entity_position: {}'.format(ship_position, entity_position))

        # Work out the closest point they meet
        ship_velocity_step = Position(ship.vel_x/VELOCITY_STEPS, ship.vel_y/VELOCITY_STEPS)
        entity_velocity_step = Position(entity.vel_x / VELOCITY_STEPS, entity.vel_y / VELOCITY_STEPS)

        logging.info('velocity step ship: {}   entity: {}'.format(ship_velocity_step, entity_velocity_step))

        min_distance = math.inf
        velocity_step = None
        min_ship_position = None
        min_entity_position = None

        for step in range(VELOCITY_STEPS):
            current_ship_position = Position(ship_position.x + ship_velocity_step.x * step,
                                             ship_position.y + ship_velocity_step.y * step)
            current_entity_position = Position(entity_position.x + entity_velocity_step.x * step,
                                               entity_position.y + entity_velocity_step.y * step)

            distance = current_ship_position.calculate_distance_between(current_entity_position)
            if distance < min_distance:
                min_distance = distance
                velocity_step = step

                min_ship_position = current_ship_position
                min_entity_position = current_entity_position

        logging.info('min distance {}'.format(min_distance))

        # Required distance
        required_distance = ship.radius + entity.radius
        distance_to_deflect = required_distance - min_distance

        logging.info('required_distance {}, distance_to_reflect'.format(required_distance, distance_to_deflect))

        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            logging.info('Ship is docked')
        elif ship.magnitude == 0:
            logging.info('Entity is not moving atm (it may have just started to dock)')
        else:
            new_ship_angle = self.get_deflected_angle(ship, entity, distance_to_deflect * ship_modifier)
            ship.thrust(ship.magnitude, new_ship_angle)
            #logging.info('new_ship_angle {}, ship.magnitude'.format(ship.magnitude, new_ship_angle))

        if isinstance(entity, hlt.entity.Planet):
            logging.info('Entity is planet')
        elif entity.docking_status != entity.DockingStatus.UNDOCKED:
            logging.info('Entity is docked')
        elif entity.magnitude == 0:
            logging.info('Entity is not moving atm (it may have just started to dock)')
        else:
            new_entity_angle = self.get_deflected_angle(entity, ship, distance_to_deflect * entity_modifier)
            entity.thrust(entity.magnitude, new_entity_angle)

            logging.info('new_entity_angle {}, entity.magnitude'.format(new_entity_angle, entity.magnitude))

    def resolve_multi_target_collision(self, ship, entity, collision, collision_map, game_map, swapped=False):
        if ship.magnitude == 0:
            return

        # find the average angle between the ships
        angles_to_entities = []
        seen_entities = []
        entities = []
        for collision in self.previous_collisions[ship.id]:
            if collision[1].id in seen_entities:
                continue
            seen_entities.append(collision[1].id)
            angles_to_entities.append(ship.calculate_angle_between(collision[1]))
            entities.append(collision[1])

        fixed_entity_count = 0
        for fixed_entity in entities:
            if fixed_entity.magnitude == 0:
                fixed_entity_count += 1

        if fixed_entity_count < 2:
            logging.info('Some tried to sneak through {}'.format(self.turn))
            if swapped:
                return self.avoid_collision(entity, ship, collision[2])
            else:
                return self.avoid_collision(ship, entity, collision[2])

        max_angle_before_addjust = max(angles_to_entities)
        adjusted_angles = [x if x > (max_angle_before_addjust - 180) else x + 360 for x in angles_to_entities]

        average_angle = sum(adjusted_angles) / len(adjusted_angles)
        target_angle = ship.calculate_angle_between(ship.target)

        if (max_angle_before_addjust - 180) > target_angle:
            target_angle += 360

        if average_angle < target_angle:
            entity_angle = max(adjusted_angles)
            deflection_direction = 1
        else:
            entity_angle = min(adjusted_angles)
            deflection_direction = -1

        entity = entities[adjusted_angles.index(entity_angle)]
        distance_to_entity = ship.calculate_distance_between(entity)

        new_angle = math.degrees(math.atan((entity.radius + ship.radius)/distance_to_entity))

        error = 4 / ship.magnitude

        if deflection_direction > 0:
            new_angle = int(math.ceil(entity_angle + new_angle + error))
        else:
            new_angle = int(math.floor(entity_angle - new_angle - error))

        ship.thrust(ship.magnitude, new_angle)

        self.rotate_for_solution(game_map, collision_map, ship, deflection_direction)

        logging.info('collision new_entity_angle {}, entity.magnitude'.format(new_angle, ship.magnitude))

    def rotate_for_solution(self, game_map, collision_map, ship, rotation):
        collisions = process_event_one_ship(game_map, collision_map, ship)
        if len(collisions) == 0:
            return

        original_angle = ship.angle

        additional_angle = 10

        for _ in range(20):
            ship.thrust(ship.magnitude, ship.angle + (additional_angle * rotation))

            collisions = process_event_one_ship(game_map, collision_map, ship)
            if len(collisions) == 0:
                return
        ship.thrust(0, 0)
        logging.info('Unable to rotate to find solution to collision, thrust set to 0')

    def check_for_collision_map_errors(self, collision, collision_map, game_map):
        logging.info("Checking for movememnt issues...")
        try:
            ship = game_map.get_player(collision[1][0]).get_ship(collision[1][1])
        except:
            # Not sure why just seems bad....
            return

        if ship.magnitude == 0:
            # This ship don't care about this...
            return

        if collision[3] < 0.1:
            if collision[2][0] is None:
                # entity = game_map.get_planet(collision[2][1])
                self.rotate_for_solution(game_map, collision_map, ship, -1)
                logging.info('There is no possible solution for this collision (iter 10 + planet), magnitude set to 0')
                return
            else:
                entity = game_map.get_player(collision[2][0]).get_ship(collision[2][1])
                distance = ship.calculate_distance_between(entity)
                if distance > (ship.radius + entity.radius):
                    logging.info('Map error found')
                    angle_to_target = ship.calculate_angle_between(ship.target)
                    angle_to_entity = ship.calculate_angle_between(entity)

                    if angle_to_entity - 180 > angle_to_target:
                        angle_to_target += 360

                    if abs(angle_to_entity - angle_to_target) > 90:
                        # The ship is trying to move away from the entity let it do it
                        angle_to_head = angle_to_target
                    else:
                        # Just try and move away from it
                        angle_to_head = angle_to_entity - 180

                    for thrust in range(7, 0, -1):
                        ship.thrust(ship.magnitude, angle_to_target)
                        logging.info('Call to process_event_one_ship')
                        collisions = process_event_one_ship(game_map, collision_map, ship)
                        collision_found = False
                        for collision in collisions:
                            if collision[1][1] != ship.id or collision[2][1] != ship.id or \
                                            collision[1][1] != entity.id or collision[2][1] != entity.id:
                                collision_found = True
                        if not collision_found:
                            return
        logging.info('There is no possible solution for this collision (iter 10 + end), magnitude set to 0')
        self.rotate_for_solution(game_map, collision_map, ship, -1)

    def direction_to_deflect(self, entity1, entity2):
        entity1.angle = make_angle_positive(entity1.angle)

        # Determine the direction to deflect
        angle_to_entity = make_angle_positive(entity1.calculate_angle_between(entity2))
        if (entity1.angle < angle_to_entity) and (entity1.angle + 180 > angle_to_entity):
            return -1
        elif angle_to_entity < ((entity1.angle + 180) % 360) and ((entity1.angle + 180) % 360) < 180:
            return -1
        else:
            return 1

    def get_deflected_angle(self, entity1, entity2, deflection_distance):
        if entity1.magnitude == 0:
            return entity1.magnitude

        deflection_direction = self.direction_to_deflect(entity1, entity2)

        logging.info('Deflection angle args: deflection_distance: {}, entity1.magnitude: {}'.format(deflection_distance, entity1.magnitude))

        # Solve for isosceles triangle
        # https://math.stackexchange.com/questions/541824/how-do-i-find-the-base-angles-without-a-vertex-angle-in-a-isosceles-triangle
        #print(deflection_distance, entity1.magnitude)

        #try:
        deflection_angle = math.degrees(math.asin((deflection_distance/2) / entity1.magnitude))*2
        #except:
        logging.info('Error with deflection_angle: math.asin(({}/2) / {})'.format(deflection_distance, entity1.magnitude))

        new_angle = make_angle_positive(entity1.angle + (deflection_angle * deflection_direction))

        error = 4 / entity1.magnitude

        if deflection_direction > 0:
            new_angle = int(math.ceil(new_angle + error))
        else:
            new_angle = int(math.floor(new_angle - error))

        return new_angle

    def remove_event_duplicates(self, events):
        unique_events = []

        for event in events:
            if event[0] != 'Collision':
                continue

            if event[1][0] is None:
                key = [event[2], event[1]]
            elif  event[2][0] is None:
                key = [event[1], event[2]]
            elif event[1][0] != event[2][0]:
                if event[1][0] > event[2][0]:
                    key = [event[2], event[1]]
                else:
                    key = [event[1], event[2]]
            else:
                if event[1][1] > event[2][1]:
                    key = [event[2], event[1]]
                else:
                    key = [event[1], event[2]]

            reformatted_event = ['Collision'] + key + [event[3]]

            if reformatted_event not in unique_events:
                unique_events.append(reformatted_event)

        return unique_events


if __name__ == "__main__":
    import pickle

    pathfinder = pickle.load(open("objects/pathfinder-82.p", "rb"))
    game_map = pickle.load(open("objects/game_map-82.p", "rb"))

    pathfinder.resolve_collisions(game_map)