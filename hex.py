from graphics import *
import shapely.geometry as s
import math
import random
import heapq
import time
import copy
import sqlite3
import MySQLdb as db

from multiprocessing.dummy import Pool as ThreadPool 
import threading


lock = threading.Lock()

BOARD_SIZE = 3

class bcolors:
	RED = '\033[91m'
	BLUE = '\u001b[34m'
	BLACK = '\u001b[30m'
	WHITE = '\u001b[37m'

class Board:
	def __init__(self, dims):
		self.dims = dims
		self.board = []
		for i in range(dims[0]):
			self.board.append([])
			for j in range(dims[1]):
				self.board[i].append(0)

	def get_node(self, pos):
		return self.board[pos[0]][pos[1]]

class Graphics:
	win = None
	def __init__(self, board):
		self.win = GraphWin(width = 860, height = 860, autoflush=False)
		self.board = board
		self.update_board(board)
		#self.win.getMouse()

	def clear(self, win):
		for item in win.items[:]:
			item.undraw()
		win.update()

	def update_board(self, board):
		self.board = board
		for i in range(self.board.dims[0]):
			for j in range(self.board.dims[1]):
					hex = self.hexagon(29, 500-i*26+j*26, i*45+50+j*45)
					if i == 0 and j == 0 or  \
						i == 0 and j == self.board.dims[1]-1 or \
						i == self.board.dims[0]-1 and j == 0 or \
						i == self.board.dims[0]-1 and j == self.board.dims[1]-1: 
						hex.setOutline('green')
					elif j == 0 or j == self.board.dims[1]-1: hex.setOutline('blue')
					elif i == 0 or i == self.board.dims[0]-1: hex.setOutline('red')
					if board.board[i][j] == 'B': hex.setFill('blue')
					elif board.board[i][j] == 'R': hex.setFill('red')
					hex.draw(self.win)
		self.win.update()

	def hexagon(self, r, x, y):
		points = []
		for i in range(6):
			points.append(Point(x + r*math.cos(i*2*math.pi/6), y + r*math.sin(i*2*math.pi/6)))
		return self.rotate_polygon(Polygon(points), 30)

	def get_click(self):
		while True:
			click = self.win.getMouse()
			p1 = (click.x, click.y)

			for i in range(self.board.dims[0]):
				for j in range(self.board.dims[1]):
					hex = self.hexagon(29, 500-i*26+j*26, i*45+50+j*45)
					hex_points = []
					for k in hex.getPoints():
						hex_points.append((k.x, k.y))
					if s.Point(p1).within(s.Polygon(hex_points)):
						return (i,j)

		return False

	def rotate_polygon(self, polygon, degrees):
		theta = math.radians(degrees)  # Convert angle to radians
		cosang, sinang = math.cos(theta), math.sin(theta)

		points = polygon.getPoints()
		# find center point of Polygon to use as pivot
		n = len(points)
		cx = sum(p.getX() for p in points) / n
		cy = sum(p.getY() for p in points) / n

		new_points = []
		for p in points:
			x, y = p.getX(), p.getY()
			tx, ty = x-cx, y-cy
			new_x = ( tx*cosang + ty*sinang) + cx
			new_y = (-tx*sinang + ty*cosang) + cy
			new_points.append(Point(new_x, new_y))

		rotated_ploygon = polygon.clone()  # clone to get current attributes
		rotated_ploygon.points = new_points
		return rotated_ploygon

def safe_execute(cursor, sql, args, many=False, num_attempts=10):
	exception = None
	for _ in range(num_attempts):
		try:
			if many:
				cursor.executemany(sql, args)
			else:
				cursor.execute(sql, args)
		except db.OperationalError as e:
			#print('slipin')
			time.sleep(1)
			continue
			

class Hex:
	def __init__(self, b, graphics):
		self.b = b
		self.graphics = graphics
		self.current_run_board_states_red = {}
		self.current_run_board_states_blue = {}

	def run(self, conn, red=2, blue=2, lr=0.001, verbose=True, learn=True):
		t = time.time()
		c = conn.cursor()
		winner = False
		turn = 'B'
		num_turns = 0
		while not winner:
			num_turns+=1
			if turn == 'R' and red == '1' or turn == 'B' and blue == '1':
				move = self.get_move_from_click()
			else:
				move = self.run_lri(turn, self.b.board, c)
			self.play_move(move, turn)
			winner = self.is_win_state()
			if winner:
				if learn:
					if winner == 'B':
						args = [str(x).replace('\'','') for x in list(self.current_run_board_states_blue.keys())]
						sql = "SELECT * FROM states WHERE state in ({seq})".format(seq=','.join(['%s']*len(args)))
						try:
							#lock.acquire(True)
							safe_execute(c, sql, args)
							entries = c.fetchall()
						finally:
							pass#lock.release()

						args = []
						for i in range(len(entries)):
							args.append([entries[i][0]] + self.lri(list(entries[i][1:]), self.current_run_board_states_blue[list(self.current_run_board_states_blue.keys())[i]][0], lr, BOARD_SIZE**2))

						sql = "REPLACE INTO states VALUES ({seq})".format(seq=','.join(['%s']*(BOARD_SIZE**2+1)))
						try:
							#lock.acquire(True)
							safe_execute(c, sql, args, many=True)
						finally:
							pass#lock.release()
					else:
						args = [str(x).replace('\'','') for x in list(self.current_run_board_states_blue.keys())]
						sql = "SELECT * FROM states WHERE state in ({seq})".format(seq=','.join(['%s']*len(args)))
						try:
							#lock.acquire(True)
							safe_execute(c, sql, args)
							entries = c.fetchall()
						finally:
							pass#lock.release()

						args = []

						for i in range(len(entries)):
							args.append([entries[i][0]] + self.lri(list(entries[i][1:]), self.current_run_board_states_red[list(self.current_run_board_states_red.keys())[i]][0], lr, BOARD_SIZE**2))

						sql = "REPLACE INTO states VALUES ({seq})".format(seq=','.join(['%s']*(BOARD_SIZE**2+1)))

						try:
							#lock.acquire(True)
							safe_execute(c, sql, args, many=True)
						finally:
							pass#lock.release()
				
				if verbose: print(winner+" wins!")
				

			turn = 'R' if turn == 'B' else 'B'
		nt = time.time() - t
		return winner

	def get_move_from_click(self):
		while True:
			move = self.graphics.get_click()
			if move in self.possible_moves(self.b.board): return move

	def alpha_beta(self, player, heuristic, ply=1):
		infinite = float('inf')
		opponent = 'R' if player == 'B' else 'R'
		node_count = 0

		def max_value(board, alpha, beta, ply):
			if ply == 0 or not self.is_win_state() == False:
				score = heuristic(player, board)
				return score
			v = -infinite
			successors = self.get_successors(player, board)
			#nonlocal node_count
			i = 0
			for (_,s) in successors:
				node_count +=1
				v = max(v, min_value(s, alpha, beta, ply-1))
				if v >= beta:
					return v
				alpha = max(alpha, v)
			return v

		def min_value(board, alpha, beta, ply):
			if ply == 0 or not self.is_win_state() == False:
				score = heuristic(player, board)
				return score
			v = infinite
			successors = self.get_successors(player, board)
			#nonlocal node_count
			for (_,s) in successors:
				node_count += 1
				v = min(v, max_value(s, alpha, beta, ply-1))
				if v <= alpha:
					return v
				beta = min(beta, v)
			return v

		argmax = lambda keys, func: max(map(lambda key: (func(*key), key), keys))[1]
		successors = self.get_successors(player, self.b.board)

		action, state = argmax(successors, lambda a,b: min_value(b, -infinite, infinite, ply))
		self.current_run_board_states.append(self.flatten_board(state))

		return action

	def get_successors(self, player, board):
		successors = []
		moves = self.possible_moves(board)
		for move in moves:
			successors.append((move, self.play_move(move, player, execute=False)))
		return successors

	def get_neighbours(self, pos):
		neighbours = [(pos[0],pos[1]-1), (pos[0]-1,pos[1]), (pos[0]+1,pos[1]-1), \
						(pos[0]-1,pos[1]+1), (pos[0]+1,pos[1]), (pos[0],pos[1]+1)]

		return [item for item in neighbours if \
				item[0] >= 0 and \
				item[1] >= 0 and \
				item[0] <= self.b.dims[0]-1 and \
				item[1] <= self.b.dims[1]-1]

	def is_win_state(self):
		# red
		checked = [[False for i in range(self.b.dims[0])] for j in range(self.b.dims[1])]
		queue = []
		for j in range(self.b.dims[1]):
			if self.b.board[0][j] == 'R':
				heapq.heappush(queue, (0, j, self.b.board[0][j]))
				checked[0][j] = True
			while queue:
				node = heapq.heappop(queue)
				for neighbour in self.get_neighbours((node[0],node[1])):
					if neighbour and checked[neighbour[0]][neighbour[1]] == False and self.b.board[neighbour[0]][neighbour[1]] == 'R':
						if neighbour[0] == self.b.dims[0]-1: return 'R'
						heapq.heappush(queue, (neighbour[0], neighbour[1], self.b.board[neighbour[0]][neighbour[1]]))
						checked[neighbour[0]][neighbour[1]] = True

		# blue
		checked = [[False for i in range(self.b.dims[0])] for j in range(self.b.dims[1])]
		queue = []
		for i in range(self.b.dims[0]):
			if self.b.board[i][0] == 'B':
				heapq.heappush(queue, (i, 0, self.b.board[i][0]))
				checked[i][0] = True
			while queue:
				node = heapq.heappop(queue)
				for neighbour in self.get_neighbours((node[0],node[1])):
					if neighbour and checked[neighbour[0]][neighbour[1]] == False and self.b.board[neighbour[0]][neighbour[1]] == 'B':
						if neighbour[1] == self.b.dims[1]-1: return 'B'
						heapq.heappush(queue, (neighbour[0], neighbour[1], self.b.board[neighbour[0]][neighbour[1]]))
						checked[neighbour[0]][neighbour[1]] = True
		
		return False
			
	def play_move(self, move, player, execute=True):
		if execute == True:
			try:
				self.b.board[move[0]][move[1]] = player
			except:
				print(move)
				print(move[0])
				print(move[1])
				print(self.b.board)

			if self.graphics: self.graphics.update_board(self.b)
			return True
		else:
			b = [x[:] for x in self.b.board]
			b[move[0]][move[1]] = player
			return b

	def random_move(self):
		moves = self.possible_moves(self.b.board)
		return moves[random.randint(0,len(moves)-1)]

	def flatten_board(self, board):
		return tuple([item for sublist in board for item in sublist])

	def lri(self, probabilities, i, alpha, R=4):
		probabilities[i] += alpha * (1 - probabilities[i])
		for j in (y for y in range(R) if y != i):
			probabilities[j] -= alpha * probabilities[j]

		return [round(x,5) for x in probabilities]

	def run_lri(self, player, board, c):
		flat_board = self.flatten_board(board)
		sql = "SELECT * FROM states WHERE state='%s'" % str(flat_board).replace("\'","")
		try:
			#lock.acquire(True)
			safe_execute(c, sql, None)
			#c.execute(sql)
			result = c.fetchone()
		finally:
			pass#lock.release()
		if result:
			probabilities = result[1:]
		else:
			probabilities = []
			possible_moves = self.possible_moves(board)
			for i in range(BOARD_SIZE**2):
				if tuple((i//BOARD_SIZE, i%BOARD_SIZE)) in possible_moves:
					probabilities.append(round(1/len(possible_moves),5))
				else:
					probabilities.append(0)

			columns = '('+','.join('%s' for _ in range(BOARD_SIZE**2+1))+')'
			sql = "REPLACE INTO states VALUES " + columns
			args = [str(flat_board).replace("\'","")] + probabilities
			try:
				#lock.acquire(True)
				safe_execute(c, sql, args)
				c.execute(sql, args)

			finally:
				pass#lock.release()

		n = random.random()
		for i in range(len(probabilities)):
			n -= probabilities[i]
			if n <= 0:
				if player == 'R': 
					self.current_run_board_states_red[flat_board] = (i, len(probabilities))
				else:
					self.current_run_board_states_blue[flat_board] = (i, len(probabilities))
				return (i//BOARD_SIZE, i%BOARD_SIZE)
		return (BOARD_SIZE-1, BOARD_SIZE-1) # if truncation breaks code return last value

	def possible_moves(self, board):
		moves = []
		for i in range(len(board)):
			for j in range(len(board[i])):
				if board[i][j] == 0: moves.append((i,j))
		return moves

def run_threaded_games(game):
	conn = db.connect(host='localhost',
                             user='root',
                             password='',
                             db='hex',
                             charset='utf8mb4')
	#conn = db.connect(database='jaredwideman', user='postgres', host='localhost', password='pass123', port="5432")
	#conn = sqlite3.connect('hex.db', timeout=10)
	game.run(conn, verbose=False)
	conn.commit()
	conn.close()

def main():
	conn = db.connect(host='localhost',
                             user='root',
                             password='',
                             db='hex',
                             charset='utf8mb4')	#conn = sqlite3.connect('hex.db')
	c = conn.cursor()
	"""
	c.execute("DROP TABLE states;")
	c.execute("CREATE TABLE IF NOT EXISTS states (state varchar(255) primary key);")
	for i in range(BOARD_SIZE):
		for j in range(BOARD_SIZE):
			c.execute("ALTER TABLE states ADD c%s%s real" % (i,j))
	"""
	conn.commit()
	while True:
		p1 = input("\nWho is playing as RED?\n  1. Human\n  2. AI\n")
		try:
			if int(p1) >= 1 and int(p1) <= 2: break
			else: print("Invalid entry, try again.\n")
		except ValueError: 
			print("Invalid entry, try again.\n")
	while True:
		p2 = input("\nWho is playing as BLUE?\n  1. Human\n  2. AI\n")
		try:
			if int(p2) >= 1 and int(p2) <= 2: break
			else: print("Invalid entry, try again.\n")
		except ValueError: 
			print("Invalid entry, try again.\n")

	if p1 == p2 and p1 == '2':
		while True:
			learn = input("\nLearn or Play?\n  1. Learn\n  2. Play\n")
			try:
				if int(learn) >= 1 and int(learn) <= 2: break
				else: print("Invalid entry, try again.\n")
			except ValueError: 
				print("Invalid entry, try again.\n")
	else:
		learn = 2

	iterations = 5000

	results = []

	track_after = 1000

	if learn == '1':
		#conn = sqlite3.connect('hex.db', check_same_thread=False)
		#c = conn.cursor()

		num_games = 300
		num_threads = 20
		t = time.time()
		pool = ThreadPool(num_threads)
		results = pool.map(run_threaded_games, [Hex(Board((BOARD_SIZE, BOARD_SIZE)), None) for _ in range(num_games)])
		print("played " + str(num_games) + ": took " + str(time.time()-t) + " seconds on " + str(num_threads) + " threads.")
		"""
		for i in range(iterations):
			if i % track_after == 0: t = time.time()
			b = Board((BOARD_SIZE,BOARD_SIZE))
			h = Hex(b, None)
			h.run(p1, p2, verbose=False)
			if i % track_after == track_after-1: print(str(round((i+1)/iterations*100,2)) +"% - "+str(track_after)+" games took " + str(round(time.time()-t, 2)) + " seconds.\n")
		"""
	else:
		for _ in range(iterations):
			b = Board((BOARD_SIZE,BOARD_SIZE))
			g = Graphics(b)
			h = Hex(b, g)
			winner = h.run(conn, p1, p2, verbose=True, learn=False)
			results.append(winner)
			if len(results) > 10: results = results[len(results)-10:]
			r_count = 0
			for i in range(len(results)):
				if results[i] == 'R': r_count+=1
			print("red last 10 win% = " + str(100*r_count/min(10, len(results)))+ "%")
	
	conn.close()

	


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		#conn.commit()
		#conn.close()

		print('done')
		try:
			sys.exit(0)
		except SystemExit:
			os._exit(0)