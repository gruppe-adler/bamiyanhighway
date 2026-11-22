//! On every piece of the tunnel test kit (TT_). While the camera is inside one, the camera's exposure is held at one
//! level instead of the game's own: left to itself the game brightens the picture in the dark until anything with a
//! little light on it (the player's own body) glows, and brightens it by a different amount in every corner of the
//! tunnels. In an entrance it comes in by how deep under the ground the camera is. Out in the open again, the game's
//! exposure takes over. Modelled on the EoH tunnel network's EOH_ProcSight hold.
[ComponentEditorProps(category: "EoH/Tunnels", description: "Holds the camera's exposure while it is inside this tunnel piece")]
class SP_TunnelExposureComponentClass : ScriptComponentClass
{
}

class SP_TunnelExposureComponent : ScriptComponent
{
	[Attribute("0", UIWidgets.CheckBox, "An entrance: the picture darkens by how deep under the ground the camera is, not all at once")]
	protected bool m_bEntrance;

	[Attribute("0.08", UIWidgets.EditBox, "How bright the picture is held in the tunnels (the camera's exposure gain), the same by day and by night. Lower is darker")]
	protected float m_fTunnelGain;

	protected static ref array<SP_TunnelExposureComponent> s_aPieces;
	protected static float s_fGain = 0.08;
	protected static float s_fOutsideGain = 0.02;	// what the game's exposure made of the open air, last seen
	protected static float s_fHeldStops;
	protected static int s_iHeldCamera = -1;
	protected static int s_iLastFrame;
	protected static int s_iOutSince;

	//------------------------------------------------------------------------------------------------
	override void OnPostInit(IEntity owner)
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !game.InPlayMode() || System.IsConsoleApp())
			return;

		if (!s_aPieces)
		{
			s_aPieces = {};
			s_iLastFrame = System.GetTickCount();
			game.GetCallqueue().CallLater(Expose, 0, true);
		}

		s_aPieces.Insert(this);
		s_fGain = Math.Clamp(m_fTunnelGain, 0.002, 1);
	}

	//------------------------------------------------------------------------------------------------
	override void OnDelete(IEntity owner)
	{
		if (!s_aPieces)
			return;

		s_aPieces.RemoveItem(this);
		if (s_aPieces.IsEmpty())
		{
			s_aPieces = null;
			ArmaReforgerScripted game = GetGame();
			if (game)
			{
				game.GetCallqueue().Remove(Expose);
				Let(game.GetWorld());
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! 1 inside this piece, 0 outside it; in an entrance, by how deep under the ground
	protected float DarknessAt(vector pos, BaseWorld world)
	{
		IEntity owner = GetOwner();
		if (!owner || vector.DistanceSq(owner.GetOrigin(), pos) > 400)
			return 0;

		vector mins, maxs;
		owner.GetBounds(mins, maxs);
		vector local = owner.CoordToLocal(pos);
		for (int i = 0; i < 3; i++)
		{
			if (local[i] < mins[i] || local[i] > maxs[i])
				return 0;
		}

		if (!m_bEntrance)
			return 1;

		float depth = world.GetSurfaceY(pos[0], pos[2]) - pos[1];
		return Math.Clamp((depth - 0.5) / 2.5, 0, 1);
	}

	//------------------------------------------------------------------------------------------------
	//! Every frame
	protected static void Expose()
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !s_aPieces)
			return;

		BaseWorld world = game.GetWorld();
		if (!world)
			return;

		int now = System.GetTickCount();
		float frame = Math.Clamp((now - s_iLastFrame) * 0.001, 0, 0.1);
		s_iLastFrame = now;

		vector view[4];
		world.GetCurrentCamera(view);
		int camera = world.GetCurrentCameraId();
		if (s_iHeldCamera >= 0 && s_iHeldCamera != camera)
			Let(world);

		float dark;
		foreach (SP_TunnelExposureComponent piece : s_aPieces)
		{
			if (!piece)
				continue;

			dark = Math.Max(dark, piece.DarknessAt(view[3], world));
			if (dark >= 1)
				break;
		}

		float outside = Math.Log2(s_fOutsideGain);
		float target = outside + (Math.Log2(s_fGain) - outside) * dark;
		if (s_iHeldCamera < 0)
		{
			float seen = world.GetCameraHDRBrightness(camera);
			if (dark < 0.02)
			{
				// Out in the open: remember what the game's exposure makes of it, to hand back to on the way out
				if (seen > 0.001 && seen < 4)
					s_fOutsideGain = seen;

				return;
			}

			// Walking in: held from where the game's exposure is, so nothing jumps; arriving deep in: straight there
			if (dark > 0.5 || seen < 0.001 || seen > 4)
				s_fHeldStops = target;
			else
				s_fHeldStops = Math.Log2(seen);

			s_iHeldCamera = camera;
			s_iOutSince = 0;
		}

		s_fHeldStops = s_fHeldStops + (target - s_fHeldStops) * Math.Min(1, frame * 5);

		// Back out in the open and level with it: the game's own exposure again
		if (dark <= 0)
		{
			if (s_iOutSince == 0)
				s_iOutSince = now;

			if (now - s_iOutSince > 400 && Math.AbsFloat(s_fHeldStops - outside) < 0.05)
			{
				Let(world);
				return;
			}
		}
		else
		{
			s_iOutSince = 0;
		}

		world.SetCameraHDRBrightness(camera, Math.Pow(2, s_fHeldStops));
	}

	//------------------------------------------------------------------------------------------------
	//! The camera goes back to the game's own exposure
	protected static void Let(BaseWorld world)
	{
		if (s_iHeldCamera >= 0 && world)
			world.SetCameraHDRBrightness(s_iHeldCamera, -1);

		s_iHeldCamera = -1;
		s_iOutSince = 0;
	}
}
