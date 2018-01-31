import math
import logging
import hlt

from squadron import Squadron

SAFE_DISTANCE = 100

class AI:
    def __init__(self, info, pathfinder):
        self.info = info
        self.pathfinder = pathfinder

        self.game_map = None

        self.rush_ended = False
        self.rush_state = None
        self.enemy_mining = False
        self.ships_docked = False

        self.last_actions = {}
        self.current_actions = {}
        self.command_queue = []
        self.assigned_ships = []
        self.planet_assigned = []
        self.defend_against = []
        self.ship_commands = []
        self.squadrons = []

    def pre_update_actions(self):
        self.last_actions = self.current_actions.copy()
        self.current_actions = {}

    def post_update_actions(self, game_map):
        self.game_map = game_map

        self.command_queue = []
        self.assigned_ships = []
        self.planet_assigned = []
        self.defend_against = []
        self.ship_commands = []

        self.mark_squadrons_as_assigned()
        self.update_squadrons_positions()

    def update_actions(self):
        self.priorities_planets()
        self.check_for_rush()
        self.rush()
        if self.rush_ended:
            if self.check_for_losing():
                return
            self.assign_existing_to_dock()
            self.assign_existing_defenders()
            self.assign_new_defenders()
            self.assign_existing_miners()
            self.assign_new_miners()
            if self.determine_attack_numbers():
                self.assign_existing_attackers()
                self.assign_new_attackers()

    def priorities_planets(self):
        DOCK_COUNT_MULTI = 0.7
        DOCK_MULTI = 0.75
        DISTANCE_MULTI = 1

        MY_PLANET_MULTI = 3
        UNOWNED_PLANET_MULTI = 2
        ENEMY_PLANET_MULTI = 1

        TEAM_SHIP_MULTI = 2
        ENEMY_SHIP_MULTI = 1

        # Determine which planets are the most strategicly relevent
        # Consider:
        #   1. The number of docks
        #   2. Who it is owned by
        #   3. The distance from our planets
        #   4. The distance from the enemy planets
        #   5. The distance from un-owned planets
        all_planet_info = []

        for planet_data in self.info.all_planet_data:
            planet_info = {}
            planet_info['planet_id'] = planet_data['planet_id']
            planet_info['closest_team_ships'] = planet_data['closest_team_ships']
            planet_info['closest_enemy_ships'] = planet_data['closest_enemy_ships']
            planet_info['dock_score'] = planet_data['available_docks']

            if planet_data['type'] == 'mine':
                planet_info['owner_score'] = MY_PLANET_MULTI
            if planet_data['type'] == 'empty':
                planet_info['owner_score'] = UNOWNED_PLANET_MULTI
            else:
                planet_info['owner_score'] = ENEMY_PLANET_MULTI

            for i, planet in enumerate(planet_data['closest_my_planets']):
                distance = sum(planet_data['closest_my_planets_distances']) / len(planet_data['closest_my_planets_distances'])
                docks = planet.num_docking_spots
                planet_info['planet_distance_score'] = distance/math.sqrt(docks/6)

            if 'planet_distance_score' not in planet_info:
                planet_info['planet_distance_score'] = 1

            close_enemy_ships = planet_data['closest_enemy_ships_distances'][:10]
            planet_info['avg_enemy_ship_distance'] = sum(close_enemy_ships) / len(close_enemy_ships)

            close_team_ships = planet_data['closest_team_ships_distances'][:10]
            planet_info['avg_team_ship_distance'] = sum(close_team_ships) / len(close_team_ships)

            planet_info['available_docks'] = planet_data['available_docks']

            all_planet_info.append(planet_info)

        max_planet_distance_score = 0
        max_avg_enemy_ship_distance = 0
        max_avg_team_ship_distance = 0

        for planet_info in all_planet_info:
            if planet_info['planet_distance_score'] > max_planet_distance_score:
                max_planet_distance_score = planet_info['planet_distance_score']
            if planet_info['avg_enemy_ship_distance'] > max_avg_enemy_ship_distance:
                max_avg_enemy_ship_distance = planet_info['avg_enemy_ship_distance']
            if planet_info['avg_team_ship_distance'] > max_avg_team_ship_distance:
                max_avg_team_ship_distance = planet_info['avg_team_ship_distance']


        for planet_info in all_planet_info:
            numerator = (planet_info['avg_enemy_ship_distance'] / max_avg_enemy_ship_distance) * \
                        (math.sqrt(planet_info['dock_score']*DOCK_MULTI/6))
            denominator = (planet_info['avg_team_ship_distance'] /max_avg_team_ship_distance) * \
                          (planet_info['planet_distance_score'] / max_planet_distance_score)
            planet_info['total_score'] = planet_info['owner_score'] * (numerator / denominator)

        self.strategic_planets = sorted(all_planet_info, key=lambda t: t['total_score'])[::-1]

        # Allocate ships to the most strategicly relevent

        # Defend with as many ships are required, assume 1 to 1, in the future consider direction of attacking ships
        # If it is unowned and no ships within our closest ships force should be minimal (no attackers)
        # If there are some enemies in the target send some ships to attack

        # If this is a enemy owned planet send all remaining ships to support (limit to 1 per round)

        # If one of the planets is owned by the enemy, determine the strength of attack

    def assign_existing_to_dock(self):
        logging.info('Ships that are currently docked continue to be docked')
        for ship in self.game_map.get_me().all_ships():
            if ship.docking_status != ship.DockingStatus.UNDOCKED:
                self.current_actions['s{}'.format(ship.id)] = ['docked']

                logging.info('Ship {}: Remaining Docked'.format(ship.id))

    def assign_existing_defenders(self):
        # Defend planet
        # If the ship was defending before, tell it to keep defending
        logging.info('Ships that were defending before continue to defend')
        self.defend_against = []
        for ship in self.game_map.get_me().all_ships():
            if self.previous_action(ship.id) == 'defending' and not ship.in_squadron:
                previous_action = self.detailed_previous_action(ship.id)

                if self.does_enemy_ship_exist(previous_action[1]):
                    enemy_ship = self.get_ship(previous_action[1])
                    self.defend_against.append(previous_action[1])

                    self.set_attack(ship, enemy_ship)

                    logging.info('Ship {}: Continuing to Defend Against Enemy Ship id: {} '.format(
                        ship.id,
                        enemy_ship.id))

    def assign_new_defenders(self):
        logging.info('Ships that are required to defend, closest defend')
        for planet in self.info.our_planets:
            for ship in planet.all_docked_ships():
                for ship_data in self.info.all_ship_data:
                    if ship_data['ship_id'] == ship.id:
                        for i, distance in enumerate(ship_data['closest_enemy_ships_distances']):
                            if self.info.turn < 35:
                                sensitivity = 20
                            else:
                                sensitivity = 20
                            if distance < sensitivity:
                                if ship_data['closest_enemy_ships'][i].id not in self.defend_against:
                                    self.defend_against.append(ship_data['closest_enemy_ships'][i].id)
                                    ship_id = self.get_closest_friendly_to_enemy_ship(ship_data['closest_enemy_ships'][i].id)
                                    if ship_id is not None:
                                        our_ship = self.game_map.get_me().get_ship(ship_id)
                                        if ship.in_squadron:
                                            continue

                                        if our_ship.calculate_distance_between(ship_data['closest_enemy_ships'][i]) > 100:
                                            continue

                                        self.set_attack(our_ship, ship_data['closest_enemy_ships'][i])

                                        logging.info('Ship {}: Defending Against Enemy Ship id: {} '.format(
                                            our_ship.id,
                                            ship_data['closest_enemy_ships'][i].id))

    def assign_existing_miners(self):
        # Mine existing planet
        # If the ship was mining before, tell it to keep mining
        logging.info('Ships that were mining before continue to mine')
        for ship in self.game_map.get_me().all_ships():
            if not self.current_action(ship.id):
                if self.previous_action(ship.id) == 'mining':
                    previous_action = self.detailed_previous_action(ship.id)
                    planet = self.game_map.get_planet(previous_action[1])

                    if planet is None:
                        continue

                    if planet.num_docking_spots > (self.get_inbound_miners(planet.id) + len(planet.all_docked_ships())):
                        logging.info('Ship {}: Continuing to Mine Planet id: {} '.format(
                            ship.id,
                            planet.id))

                        self.set_mine(ship, planet)

    def assign_new_miners(self):
        logging.info('Heading to priority planets')
        self.planet_to_attack = None

        for planet_data in self.strategic_planets:
            # We need this to stop rushes and (I think) it improves starting
            if (self.info.largest_planet > 2 and planet_data['available_docks'] < 3) and (self.info.turn < 5):
                continue

            planet = self.game_map.get_planet(planet_data['planet_id'])

            if planet in self.info.enemy_planets:
                self.planet_to_attack = planet
                break

            while planet.num_docking_spots > (self.get_inbound_miners(planet.id) + len(planet.all_docked_ships())):
                if self.all_allocated():
                    break

                ship = None
                for possible_ship in planet_data['closest_team_ships']:
                    if 's{}'.format(possible_ship.id) not in self.current_actions:
                        ship = possible_ship
                        break

                if ship is None:
                    break

                logging.info('Ship {}: Heading to Priority Planet id: {} '.format(
                    ship.id,
                    planet.id))

                self.set_mine(ship, planet)

    def clear_attack_data(self):
        self.within_50 = 0
        self.within_100 = 0
        self.within_150 = 0
        self.within_200 = 0

        self.within_50_additional = 0
        self.within_100_additional = 0
        self.within_150_additional = 0
        self.within_200_additional = 0

        self.planet_to_attack_data = None
        self.attacked_ships = []

    def determine_attack_numbers(self):
        self.clear_attack_data()
        if self.planet_to_attack is None:
            return False
        for planet_data in self.info.all_planet_data:
            if planet_data['planet_id'] == self.planet_to_attack.id:
                self.planet_to_attack_data = planet_data
                break


        remaining_unallocated_ships = self.num_unalocated_ships()

        if remaining_unallocated_ships == 0:
            return False

        sequence = [1, 1, 2, 1, 2, 3, 1, 2, 3, 4]

        for bracket in sequence:
            if bracket == 1:
                if remaining_unallocated_ships >= self.planet_to_attack_data['enemies_within_50']:
                    self.within_50 += 1
                    remaining_unallocated_ships -= self.planet_to_attack_data['enemies_within_50']
                else:
                    self.within_50_additional = remaining_unallocated_ships
                    break
            elif bracket == 2:
                if remaining_unallocated_ships >= self.planet_to_attack_data['enemies_within_100']:
                    self.within_100 += 1
                    remaining_unallocated_ships -= self.planet_to_attack_data['enemies_within_100']
                else:
                    self.within_100_additional = remaining_unallocated_ships
                    break
            elif bracket == 3:
                if remaining_unallocated_ships >= self.planet_to_attack_data['enemies_within_150']:
                    self.within_150 += 1
                    remaining_unallocated_ships -= self.planet_to_attack_data['enemies_within_150']
                else:
                    self.within_150_additional = remaining_unallocated_ships
                    break
            elif bracket == 4:
                if remaining_unallocated_ships >= self.planet_to_attack_data['enemies_within_200']:
                    self.within_200 += 1
                    remaining_unallocated_ships -= self.planet_to_attack_data['enemies_within_200']
                else:
                    self.within_200_additional = remaining_unallocated_ships
                    break
        return True

    def assign_existing_attackers(self):
        for ship_id, action in self.last_actions.items():
            if action[0] == 'attacking':
                if ship_id not in self.current_actions:
                    our_ship = self.game_map.get_me().get_ship(int(ship_id[1:]))
                    enemy_ship = self.get_ship(action[1], enemy=True)

                    if enemy_ship and our_ship is not None:
                        self.attacked_ships.append(enemy_ship.id)
                        self.set_attack(our_ship, enemy_ship, attack=True, distance=our_ship.calculate_distance_between(enemy_ship)-1)

                        logging.info('Ship {}: Continuing to attack Enemy Ship id: {} '.format(
                            our_ship.id,
                            enemy_ship.id))

    def assign_new_attackers(self):
        logging.info('Attack ships closest to target planet')
        level_1 = self.planet_to_attack_data['enemies_within_50'] * self.within_50 + self.within_50_additional
        level_2 = self.planet_to_attack_data['enemies_within_100'] * self.within_100 + self.within_100_additional + level_1
        level_3 = self.planet_to_attack_data['enemies_within_150'] * self.within_150 + self.within_150_additional + level_2
        level_4 = self.planet_to_attack_data['enemies_within_200'] * self.within_200 + self.within_200_additional + level_3

        unallocated_ships = self.get_unallocated()
        unallocated_ships_index = 0

        additionals_added = 0
        for i, enemy_ship in enumerate(self.planet_to_attack_data['closest_enemy_ships']):
            if unallocated_ships_index >= len(unallocated_ships):
                logging.info('All Ships Allocated')
                break

            if i < level_1:
                enemy_multi = self.within_50
                additional = self.within_50_additional
            elif i < level_2:
                enemy_multi = self.within_100
                additional = self.within_100_additional
            elif i < level_3:
                enemy_multi = self.within_150
                additional = self.within_150_additional
            elif i < level_4:
                enemy_multi = self.within_200
                additional = self.within_200_additional
            else:
                logging.info('It should not get here....')
                break


            required_attackers = enemy_multi - self.attacked_ships.count(enemy_ship.id)

            actual_additionals = additional - additionals_added
            if actual_additionals > 0:
                required_attackers += 1
                additionals_added += 1

            if required_attackers <= 0:
                continue
            for _ in range(required_attackers):
                if unallocated_ships_index >= len(unallocated_ships):
                    break

                self.set_attack(unallocated_ships[unallocated_ships_index], enemy_ship, attack=True, distance=unallocated_ships[unallocated_ships_index].calculate_distance_between(enemy_ship)-1)

                logging.info('Ship {}: Attacking Ship id: {} '.format(
                    unallocated_ships[unallocated_ships_index].id,
                    enemy_ship.id))
                unallocated_ships_index += 1

    def num_unalocated_ships(self):
        return len(self.game_map.get_me().all_ships()) - len(self.current_actions)

    def get_ship(self, ship_id, enemy=False):
        for player in self.game_map.all_players():
            if enemy and player.id == self.game_map.get_me().id:
                continue
            ship = player.get_ship(ship_id)
            if ship is not None:
                return ship
        return False

    def current_action(self, ship_id):
        for id, action in self.current_actions.items():
            if id == "s{}".format(ship_id):
                return action[0]
        return False

    def previous_action(self, ship_id):
        for id, action in self.last_actions.items():
            if id == "s{}".format(ship_id):
                return action[0]

    def detailed_previous_action(self, ship_id):
        for id, action in self.last_actions.items():
            if id == "s{}".format(ship_id):
                return action

    def does_enemy_ship_exist(self, enemy_ship_id):
        for ship_data in self.info.all_enemy_ships:
            if ship_data['ship_id'] == enemy_ship_id:
                return True
        return False

    def has_action(self, ship_id):
        return "s{}".format(ship_id) in self.current_actions

    def all_allocated(self):
        if len(self.game_map.get_me().all_ships()) == len(self.current_actions):
            return True
        else:
            return False

    def get_inbound_miners(self, planet_id):
        inbound_miners = 0
        for key, value in self.current_actions.items():
            if value[0] == 'mining':
                if value[1] == planet_id:
                    inbound_miners += 1

        # logging.info('{} inbound_minders to {}'.format(inbound_miners, planet_id))
        return inbound_miners

    def get_unallocated(self):
        unallocated = []
        for ship in self.game_map.get_me().all_ships():
            if not self.has_action(ship.id):
                unallocated.append(ship)

        return unallocated

    def all_enemy_ships_attacked(self):
        #logging.info(self.defend_against)
        return len(self.info.all_enemy_ships) == len(self.defend_against)

    def set_attack(self, our_ship, enemy_ship, attack=False, distance=hlt.constants.MAX_SPEED):
        mode = 'attacking' if attack else 'defending'
        ignore = True if attack else False
        self.current_actions['s{}'.format(our_ship.id)] = [mode, enemy_ship.id]

        self.pathfinder.navigate(our_ship, enemy_ship, self.game_map)

    def set_mine(self, our_ship, planet):
        if our_ship.can_dock(planet) and not planet.is_full() and (planet.owner == self.game_map.get_me() or not planet.is_owned()):
            # don't dock if we think a rush may occur
            if not self.rush_ended and self.rush_state == 'cautious-dock':
                self.current_actions['s{}'.format(our_ship.id)] = ['mining', planet.id]
                return

            # Check that there are no enemy ships close
            for ship_data in self.info.all_ship_data:
                if ship_data['ship_id'] == our_ship.id:
                    for i, distance in enumerate(ship_data['closest_enemy_ships_distances']):
                        if self.info.turn < 35:
                            sensitivity = 20
                        else:
                            sensitivity = 20
                        if distance < sensitivity:
                            if ship_data['closest_enemy_ships'][i] not in self.defend_against:
                                self.set_attack(our_ship, ship_data['closest_enemy_ships'][i])

                                logging.info('Ship {}: Stopped Mining Defending Against Enemy Ship id: {} '.format(
                                    our_ship.id,
                                    ship_data['closest_enemy_ships'][i].id))
                                return



            logging.info('Ship {}: Starting to mine planet id: {} '.format(
                our_ship.id,
                planet.id))

            self.started_to_mine = True
            self.current_actions['s{}'.format(our_ship.id)] = ['mining', planet.id]
            our_ship.dock(planet)
            return

        self.current_actions['s{}'.format(our_ship.id)] = ['mining', planet.id]

        if planet.is_owned():
            if planet.owner != self.game_map.get_me():
                for docked_ship in planet.all_docked_ships():
                    self.pathfinder.navigate(our_ship, docked_ship, self.game_map)
                    return

        self.pathfinder.navigate(our_ship, planet, self.game_map)

    def navigate_to_own_mining_ships(self, our_ship):
        for minning_ship in self.game_map.get_me().all_ships():
            if minning_ship.docking_status != minning_ship.DockingStatus.UNDOCKED:
                self.pathfinder.navigate(our_ship, minning_ship, self.game_map)
                return

    def get_closest_friendly_to_enemy_ship(self, ship_id):
        ship_distances = []
        for ship_data in self.info.all_ship_data:
            if 's{}'.format(ship_data['ship_id']) not in self.current_actions:
                for i, enemy_ship in enumerate(ship_data['closest_enemy_ships']):
                    if ship_id == enemy_ship.id:
                        ship_distances.append(ship_data['closest_enemy_ships_distances'][i])
            else:
                ship_distances.append(10000)

        if min(ship_distances) == 10000:
            return None

        return self.info.all_ship_data[ship_distances.index(min(ship_distances))]['ship_id']

    def is_enemy_mining(self):
        for enemy in self.game_map.all_players():
            if enemy != self.game_map.get_me():
                for enemy_ship in enemy.all_ships():
                    if enemy_ship.docking_status != enemy_ship.DockingStatus.UNDOCKED:
                        return True
        else:
            return False

    def update_squadrons_positions(self):
        available_squadrons = []
        for i, squadron in enumerate(self.squadrons):
            available_squadrons.append(squadron.update_position())

        new_squadrons = []
        for i, available in enumerate(available_squadrons):
            if available:
                new_squadrons.append(self.squadrons[i])

        self.squadrons = new_squadrons

    def check_for_rush(self):
        if self.rush_ended:
            return

        minning_planet = self.game_map.get_planet(self.strategic_planets[0]['planet_id'])
        for planet_data in self.strategic_planets:
            # We need this to stop rushes and (I think) it improves starting
            if planet_data['available_docks'] >= 3:
                minning_planet = self.game_map.get_planet(planet_data['planet_id'])
                break

        distance_to_mining_planet = []
        distance_to_enemy_ships = []
        can_we_dock = False
        for ship in self.game_map.get_me().all_ships():
            distance_to_mining_planet.append(ship.calculate_distance_between(minning_planet))

            if ship.can_dock(minning_planet):
                can_we_dock = True

            for enemy in self.game_map.all_players():
                if enemy != self.game_map.get_me():
                    for enemy_ship in enemy.all_ships():
                        distance_to_enemy_ships.append(enemy_ship.calculate_distance_between(ship))

        closest_distance_to_enemy_ships = min(distance_to_enemy_ships)
        closest_distance_to_mining_planet = min(distance_to_mining_planet)

        enemy_distance_to_mining_planets = []
        for enemy in self.game_map.all_players():
            if enemy != self.game_map.get_me():
                for enemy_ship in enemy.all_ships():
                    enemy_distance_to_mining_planets.append(enemy_ship.calculate_distance_between(minning_planet))

        closest_enemy_to_mining_planet = min(enemy_distance_to_mining_planets)

        number_of_players = len(self.game_map.all_players())

        units_until_attack = closest_enemy_to_mining_planet - closest_distance_to_mining_planet

        # TYPES OF RUSH STATE
        # Basic Rush - if within safe distance at the start just head towards the enemy
        # Advanced Rush - If Basic Rush gets within 30 units and the enemy is not docked swap to formation
        # Cautious Dock - Move towards the mining planet but don't dock unless the enemy is outside of safe dock range
        # Dock rush - if the enemy is with safe range when we get to the mining planet swap to advanced rush

        enemy_started_mining_this_turn = False
        if not self.enemy_mining:
            self.enemy_mining = self.is_enemy_mining()
            if self.enemy_mining:
                enemy_started_mining_this_turn = True

        logging.info('closest_enemy_to_mining_planet: {}'.format(closest_enemy_to_mining_planet))
        logging.info('closest_distance_to_enemy_ships: {}'.format(closest_distance_to_enemy_ships))
        logging.info('closest_distance_to_mining_planet: {}'.format(closest_distance_to_mining_planet))
        logging.info('number_of_players: {}'.format(number_of_players))
        logging.info('units_until_attack: {}'.format(units_until_attack))
        logging.info('enemy_mining: {}'.format(self.enemy_mining))
        logging.info('enemy_started_mining_this_turn: {}'.format(enemy_started_mining_this_turn))
        logging.info('can_we_dock: {}'.format(can_we_dock))

        if number_of_players > 2:
            self.rush_ended = True

        if self.info.turn == 0 and closest_distance_to_enemy_ships < SAFE_DISTANCE:
            self.rush_state = 'advanced-rush'
        elif enemy_started_mining_this_turn and closest_distance_to_enemy_ships < SAFE_DISTANCE:
            self.rush_state = 'advanced-rush'
        elif self.rush_state == 'basic-rush' and not self.enemy_mining and closest_distance_to_enemy_ships < 50:
            self.rush_state = 'advanced-rush'
        elif self.rush_state == 'cautious-dock' and closest_distance_to_enemy_ships < 50:
            self.rush_state = 'advanced-rush'
        elif self.rush_state == 'defensive-dock' and self.enemy_mining:
            self.rush_ended = True
        elif can_we_dock and closest_distance_to_enemy_ships > (SAFE_DISTANCE-5):
            # -7 as we are one movement up
            self.rush_state = 'defensive-dock'
        elif self.rush_state not in ['defensive-dock', 'advanced-rush', 'basic-rush'] and self.enemy_mining:
            self.rush_ended = True
        elif self.rush_state not in ['defensive-dock', 'advanced-rush', 'basic-rush']:
            self.rush_state = 'cautious-dock'
        elif self.rush_state not in ['advanced-rush', 'basic-rush']:
            self.rush_state = 'defensive-dock'

        logging.info("Rush State: {}".format(self.rush_state))

    def rush(self):
        if self.rush_ended:
            return

        if self.rush_state == 'basic-rush':
            self.basic_rush()
        elif self.rush_state == 'cautious-dock':
            self.assign_existing_miners()
            self.assign_new_miners()
        elif self.rush_state == 'defensive-dock':
            self.defensive_dock()
        elif not self.rush_ended:
            self.advanced_rush()

    def defensive_dock(self):
        mining_ship = None
        for ship in self.game_map.get_me().all_ships():
            if ship.docking_status != ship.DockingStatus.UNDOCKED:
                mining_ship = ship
                self.ships_docked = self.info.turn
                break
        logging.info('mining_ship: {}'.format(mining_ship))

        if not self.ships_docked or self.info.turn < self.ships_docked + 3:
            self.assign_existing_to_dock()
            self.assign_existing_miners()
            self.assign_new_miners()

        if mining_ship is None and self.info.turn > 9:
            # all our miners are dead
            logging.info('Changed to advanced-rush')
            self.rush_state = 'advanced-rush'

        if mining_ship is not None and self.info.turn > 9:
            for ship in self.game_map.get_me().all_ships():
                if ship.docking_status == ship.DockingStatus.UNDOCKED:
                    self.pathfinder.navigate(ship, mining_ship, self.game_map)

    def advanced_rush(self):
        ships = self.game_map.get_me().all_ships()

        if len(self.squadrons) == 0:
            ships = [ship.id for ship in ships]
            squadron = Squadron(self.game_map, ships)
            self.squadrons.append(squadron)

        closet_enemy_ship = self.info.all_ship_data[0]['closest_enemy_ships'][0]
        closest_distance = math.inf
        for player in self.game_map.all_players():
            for ship in player.all_ships():
                if ship.docking_status != ship.DockingStatus.UNDOCKED:
                    distance = self.squadrons[0].calculate_distance_between(ship)
                    if distance < closest_distance:
                        closet_enemy_ship = ship
                        closest_distance = distance

        distance = self.squadrons[0].calculate_distance_between(closet_enemy_ship)

        thrust = 7 if distance > 7 else distance
        angle = self.squadrons[0].calculate_angle_between(closet_enemy_ship)

        focus = self.squadrons[0].calculate_distance_between(closet_enemy_ship)
        heading = self.squadrons[0].calculate_angle_between(closet_enemy_ship)

        #self.squadrons[0].navigate(thrust, angle, closet_enemy_ship, focus=focus, heading=heading)
        self.pathfinder.navigate(self.squadrons[0], closet_enemy_ship, self.game_map)

    def basic_rush(self):
        ship_data = self.info.all_enemy_ships[0]
        enemy_ship = self.get_ship(ship_data['ship_id'])
        for my_ship in self.game_map.get_me().all_ships():
            self.pathfinder.navigate(my_ship, enemy_ship, self.game_map)

    def mark_squadrons_as_assigned(self):
        all_ships = self.game_map.get_me().all_ships()
        for i, squadron in enumerate(self.squadrons):
            for ship in squadron.ships:
                if ship in all_ships:
                    self.current_actions['s{}'.format(self.game_map.get_me().all_ships()[ship])] = ['squadron', i]



    def check_for_losing(self):
        number_of_players = len(self.game_map.all_players())
        my_strength = 0
        other_player_strength = []

        if number_of_players > 2:
            # Get relative strenght of all the enemies
            for player in self.game_map.all_players():
                docked_ships = 0
                undocked_ships = 0

                for ship in player.all_ships():
                    if ship.docking_status == ship.DockingStatus.UNDOCKED:
                        docked_ships += 1
                    else:
                        undocked_ships += 1

                strength = docked_ships * 2 + undocked_ships

                if player == self.game_map.get_me():
                    my_strength = strength
                else:
                    other_player_strength.append(strength)

            for strength in other_player_strength:
                if strength > my_strength * 3:
                    self.run_away()
                    return True
        return False

    def run_away(self):
        for ship in self.game_map.get_me().all_ships():
            if ship.docking_status == ship.DockingStatus.UNDOCKED:
                options = [[5,5], [self.game_map.width-5, 5], [5, self.game_map.height-5], [self.game_map.width-5, self.game_map.height-5]]
                shortest_distance = math.inf
                shortest_point = None
                for i, option in enumerate(options):
                    distance = ship.calculate_distance_between(hlt.entity.Position(option[0], option[1]))
                    if distance < shortest_distance:
                        shortest_point = hlt.entity.Position(option[0], option[1])
                        shortest_distance = distance
                self.pathfinder.navigate(ship, shortest_point, self.game_map)
            else:
                ship.undock()