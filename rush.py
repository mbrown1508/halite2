import hlt
import logging
import time

from pathfinder import Pathfinder
from info import Info
from angularai import AI

class HaliteBot:
    def __init__(self):
        bot_name = "Rush"
        logging.info("Starting bot {}".format(bot_name))

        self.game = hlt.Game(bot_name)

        self.pathfinder = Pathfinder()
        self.info = Info()
        self.ai = AI(self.info, self.pathfinder)

        self.game_map = None

    def run(self, debug=False, setup_debug=False):
        while True:
            logging.info('---TURN {}---'.format(self.info.turn+1))

            if not debug:
                self.ai.pre_update_actions()
                self.game_map = self.game.update_map()
                if setup_debug:
                    import pickle
                    pickle.dump(self, open("objects/game_map-{}.p".format(self.info.turn+1), "wb"))

            self.ai.post_update_actions(self.game_map)
            self.start_turn_timer()
            self.info.update_info(self.game_map)

            ship_data = self.info.all_enemy_ships[0]
            enemy_ship = self.ai.get_ship(ship_data['ship_id'])
            for my_ship in self.game_map.get_me().all_ships():
                self.pathfinder.navigate(my_ship, enemy_ship, self.game_map)

            self.pathfinder.resolve_collisions(self.game_map)
            self.log_all_commands()

            self.log_turn_time_info()

    def log_all_commands(self):
        command_queue = []
        for ship in self.game_map.get_me().all_ships():
            command = ship.get_event()
            if command and command is not None:
                command_queue += command
        logging.info(command_queue)
        self.game.send_command_queue(command_queue)

    def start_turn_timer(self):
        self.total0 = time.time()

    def end_turn_timer(self):
        if self.info.turn == 0:
            self.longest_turn = 0
        self.total1 = time.time()
        time_taken = self.total1 - self.total0
        return time_taken

    def remaining_turn_time(self):
        total1 = time.time()
        return total1 - self.total0

    def log_turn_time_info(self):
        total_turn_time = self.end_turn_timer()
        if self.info.turn > 10:
            if total_turn_time > self.longest_turn:
                self.longest_turn = total_turn_time
        logging.info('Total turn time: {}'.format(total_turn_time))
        logging.info('Longest turn time: {}'.format(self.longest_turn))

if __name__ == "__main__":
    setup_debug = False
    debug = False
    turn = 7

    if setup_debug and not debug:
        import shutil
        import os
        try:
            shutil.rmtree('/Users/skippy/Programming/halite2/objects')
        except:
            pass
        os.mkdir('objects')

    if not debug:
        bot = HaliteBot()
        bot.run(debug=debug, setup_debug=setup_debug)
    else:
        import pickle
        game_map = pickle.load(open("objects/game_map-{}.p".format(turn), "rb"))
        game_map.run(True)
