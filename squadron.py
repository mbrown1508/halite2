import math
import hlt
import logging

from pathfinder import Pathfinder


SQUADRON_SPREAD = 0.1
TARGET_FUDGE = 2

class Squadron:
    def __init__(self, game_map, ships):
        self.game_map = game_map
        self.id = min(ships)
        self.ships = ships

        self.vel_x = 0
        self.vel_y = 0
        self.magnitude = 0
        self.angle = 0

        self.target = None

        self.formation = 'ender'
        self.focus = None
        self.radius = None

        self.pathfinder = Pathfinder()

        self.position_modifier = []
        if self.formation == 'ender':
            self.inner_ring_distance = 0.5 * 2 + SQUADRON_SPREAD
            self.outer_ring_distance = 0.5 * 4 + SQUADRON_SPREAD * 2

            self.position_modifier.append((0,0))
            for angle in range(0, 360, 60):
                self.position_modifier.append((self.inner_ring_distance, angle))
            for angle in range(0, 360, 30):
                self.position_modifier.append((self.outer_ring_distance, angle))

            self.max_size = 19

        if self.formation == '3':
            self.distance_between_ships = 0.5 * 2 + SQUADRON_SPREAD
            self.max_size = 3

        for ship in self.ships:
            self.game_map.get_me().get_ship(ship).in_squadron = True

        self.distance_between_ships = 0.5 * 2 + SQUADRON_SPREAD

        self.update_position()
        self.x, self.y = self.get_center_point(self.ships)

    def update_position(self):
        self.reset_events()

        available_ships = [ship.id for ship in self.game_map.get_me().all_ships()]
        self.ships = [ship for ship in self.game_map.get_me().all_ships() if ship.id in available_ships]

        if len(self.ships) > 0:
            self.x = self.ships[0].x
            self.y = self.ships[0].y
            self.radius = self.ships[0].radius
            if len(self.ships) > 1:
                self.radius = self.ships[0].radius * 3 + SQUADRON_SPREAD
            if len(self.ships) > 7:
                self.radius = self.ships[0].radius * 5 + (SQUADRON_SPREAD * 2)
        else:
            return False
        return True

    def thrust(self, magnitude, angle, target, focus=4, heading=None):
        self.heading = angle if heading is None else heading
        self.focus = focus

        self.magnitude = magnitude

        #safe_distance = self.pathfinder.calculate_safe_distance_from_entity(self, target)
        #safe_distance = 7
        #if self.magnitude > safe_distance:
        #    self.magnitude = math.floor(safe_distance)
        if self.magnitude > hlt.constants.MAX_SPEED:
            # self.magnitude = hlt.constants.MAX_SPEED
            raise(Exception('Magnitude of {} is greater than 7'.format(self.magnitude)))

        self.angle = (round(angle) + 720) % 360

        self.vel_x = self.magnitude * math.cos(math.radians(self.angle))
        self.vel_y = self.magnitude * math.sin(math.radians(self.angle))

        if target is not None:
            self._stored_magnitude = self.magnitude
            self._stored_angle = self.angle

            self.target = target
            self.update_distance_to_target()

        if self._stored_magnitude != self.magnitude or self._stored_angle != self.angle:
            self.update_distance_to_target()

        if self.formation == '3':
            center_position = hlt.entity.Position(self.x, self.y)
            angle_modifier = math.degrees(math.acos(self.distance_between_ships / 2 / (self.focus+self.ships[0].radius)))

            self.position_modifier = [
                (1.1, angle_modifier + heading),
                (0,0),
                (1.1, -angle_modifier + heading)
            ]

        elif self.formation == 'ender':
            center_position = hlt.entity.Position(self.x, self.y)

        out_of_position = 0
        for i, ship in enumerate(self.ships):
            target_position = self.get_position_for_x_y_angle_magnitude(center_position.x + self.vel_x, center_position.y + self.vel_y, self.position_modifier[i][0], self.position_modifier[i][1])
            raw_distance = ship.calculate_distance_between(target_position)
            angle = ship.calculate_angle_between(target_position)

            distance = round(raw_distance)

            # There are often small differences but we don't really want to move at 6 every turn because of this.
            logging.info('Distance to formation position: {}'.format(distance))

            if distance > 7:
                out_of_position += 1
                thrust = 7
            else:
                thrust = distance

            ship.thrust(thrust, angle, target_position)

        if out_of_position / len(self.ships) > 0.5 and self.calculate_distance_between(self.target):
            logging.info('Out of Position')
            new_magintude = self.magnitude - 1
            if new_magintude >= 0:
                self.thrust(self.magnitude-1, self.angle, self.target, self.focus, self.heading)

        out_of_position = 0
        for i, ship in enumerate(self.ships):
            target_position = self.get_position_for_x_y_angle_magnitude(center_position.x + self.vel_x, center_position.y + self.vel_y, self.position_modifier[i][0], self.position_modifier[i][1])
            raw_distance = ship.calculate_distance_between(target_position)
            angle = ship.calculate_angle_between(target_position)

            distance = round(raw_distance)

            # There are often small differences but we don't really want to move at 6 every turn because of this.
            logging.info('Distance to formation position: {}'.format(distance))

            if distance > 7:
                out_of_position += 1
                thrust = 7
            else:
                thrust = distance

            #self.pathfinder.navigate()
            ship.thrust(thrust, angle, target_position)

        if out_of_position / len(self.ships) > 0.5 and self.calculate_distance_between(self.target):
            logging.info('Out of Position')
            new_magintude = self.magnitude - 1
            if new_magintude >= 0:
                self.thrust(self.magnitude-1, self.angle, self.target, self.focus, self.heading)


    def update_distance_to_target(self):
        if isinstance(self.target, hlt.entity.Planet) or isinstance(self.target, hlt.entity.Ship):
            distance_to_target = self.calculate_distance_between(self.target)
            angle_to_target = self.calculate_angle_between(self.target)

            distance_to_avoid_collision = distance_to_target - self.radius - self.target.radius - TARGET_FUDGE

            planet_x = self.target.x - distance_to_avoid_collision * math.cos(math.radians(angle_to_target))
            planet_y = self.target.y - distance_to_avoid_collision * math.sin(math.radians(angle_to_target))

            position = hlt.entity.Position(planet_x, planet_y)
        else:
            position = self.target

        final_location = self.get_final_location()
        self.distance_to_target = hlt.entity.Position(final_location[0], final_location[1]).calculate_distance_between(
            position)

        return self.distance_to_target

    def get_final_location(self):
        return [self.x + self.vel_x, self.y + self.vel_y]

    def reset_events(self):
        self.docking_planet = None
        self.vel_x = 0
        self.vel_y = 0
        self.docking_planet = None
        self.target = None

    def get_center_point(self, ships):
        x, y, count = 0, 0, 0
        for ship in ships:
            x += ship.x
            y += ship.y
            count += 1
        return x/count, y/count

    def get_position_for_x_y_angle_magnitude(self, x, y, magnitude, angle):
        target_x = magnitude * math.cos(math.radians(angle)) + x
        target_y = magnitude * math.sin(math.radians(angle)) + y
        return hlt.entity.Position(target_x, target_y)

    def __str__(self):
        return "Squadron {} (id: {}) at position: (x = {}, y = {}), with radius = {} with velocity: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y, self.radius, self.vel_x, self.vel_y)

    def calculate_distance_between(self, target):
        """
        Calculates the distance between this object and the target.

        :param Entity target: The target to get distance to.
        :return: distance
        :rtype: float
        """
        return math.sqrt((target.x - self.x) ** 2 + (target.y - self.y) ** 2)

    def calculate_angle_between(self, target):
        """
        Calculates the angle between this object and the target in degrees.

        :param Entity target: The target to get the angle between.
        :return: Angle between entities in degrees
        :rtype: float
        """
        return math.degrees(math.atan2(target.y - self.y, target.x - self.x)) % 360